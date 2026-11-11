"""Surgically patch files inside a Settlers 7 .bba archive.

Strategy: append the new file blob where the directory used to start, then
rewrite the directory and header. Every untouched entry keeps its original
bytes and its original CRC values, so the blast radius is one file.
"""
import gzip, io, os, shutil, struct, sys, zlib
from bba import (BBA, M, ONE_MIB, HEAD_KEYS, FILE_KEYS, PROD_HEAD_DELTA,
                 PROD_HEAD_LOOP, PROD_FILE_DELTA, PROD_FILE_LOOP,
                 decrypt, encrypt, to_u32, from_u32, encrypt_compressed)


def compress_entry(data, name_len):
    """gzip + per-chunk header encryption, as the engine expects (type 17)."""
    buf = io.BytesIO()
    with gzip.GzipFile(fileobj=buf, mode="wb", compresslevel=9, mtime=0) as g:
        g.write(data)
    raw = buf.getvalue()
    out = bytearray()
    for off in range(0, len(raw), ONE_MIB):
        chunk = raw[off:off + ONE_MIB]
        if len(chunk) >= 16:
            chunk = encrypt_compressed(chunk, name_len)
        out += chunk
    return bytes(out)


def patch(archive_path, replacements, out_path=None, backup=True):
    """replacements: {archive_name: new_bytes}. archive_name uses backslashes."""
    a = BBA(archive_path)
    by_name = {e.name: e for e in a.entries}
    for n in replacements:
        if n not in by_name:
            raise KeyError("no such entry in archive: %r" % n)

    src = open(archive_path, "rb").read()
    dir_enc_len = a.dir_length
    a.f.close()

    # --- rebuild directory blob (plaintext uint list) with updated entries ---
    d = list(a.dirblob)
    new_data = bytearray()
    cursor = a.dir_offset  # new blobs start where the directory used to be

    for name, content in replacements.items():
        e = by_name[name]
        if e.ftype != 17:
            raise NotImplementedError("only zlib entries (type 17) supported: %s" % name)
        blob = compress_entry(content, e.name_len)
        i = e.raw_off // 4
        d[i + 2] = len(content) & M                     # DecompressedFileSize
        d[i + 3] = zlib.crc32(content) & M              # DecompressedCrc32
        d[i + 6] = cursor & M                           # FileOffset
        d[i + 8] = len(blob) & M                        # CompressedFileSize
        d[i + 9] = zlib.crc32(blob) & M                 # CompressedCrc32
        new_data += blob
        cursor += len(blob)

    # --- encrypt directory, recompute header ---
    dir_plain = list(d)
    encrypt(dir_plain, FILE_KEYS, PROD_FILE_DELTA, PROD_FILE_LOOP)
    dir_enc = from_u32(dir_plain)
    assert len(dir_enc) == dir_enc_len, "directory size changed unexpectedly"

    hdr_block = to_u32(src[16:16 + a.header_size])
    decrypt(hdr_block, HEAD_KEYS, PROD_HEAD_DELTA, PROD_HEAD_LOOP)
    hdr_block[0] = cursor & M                  # new directory offset
    hdr_block[3] = zlib.crc32(dir_enc) & M     # CRC over encrypted directory
    encrypt(hdr_block, HEAD_KEYS, PROD_HEAD_DELTA, PROD_HEAD_LOOP)

    out = bytearray()
    out += src[:16]
    out += from_u32(hdr_block)
    out += src[16 + a.header_size:a.dir_offset]   # untouched original data
    out += new_data
    out += dir_enc

    out_path = out_path or archive_path
    if backup and out_path == archive_path:
        bak = archive_path + ".orig"
        if not os.path.exists(bak):
            shutil.copy2(archive_path, bak)
            print("[backup] %s" % bak)
    tmp = out_path + ".tmp"
    open(tmp, "wb").write(bytes(out))
    os.replace(tmp, out_path)
    print("[ok] wrote %s (%d bytes, was %d)" % (out_path, len(out), len(src)))
    return out_path


def verify(archive_path, expect):
    """Re-open the archive with the reader and confirm content round-trips."""
    a = BBA(archive_path)
    by_name = {e.name: e for e in a.entries}
    ok = True
    for name, content in expect.items():
        got = a.read(by_name[name])
        same = got == content
        ok &= same
        print("[verify] %-40s %s (%d bytes)" % (name, "OK" if same else "MISMATCH", len(got)))
    # sanity: every other entry still decodes
    bad = 0
    for e in a.entries:
        if e.ftype != 17:
            continue
        try:
            data = a.read(e)
            if (zlib.crc32(data) & M) != e.dec_crc:
                bad += 1
                print("[verify] CRC mismatch: %s" % e.name)
        except Exception as ex:
            bad += 1
            print("[verify] FAILED to read %s: %s" % (e.name, ex))
    print("[verify] %d entries checked, %d broken" % (len(a.entries), bad))
    return ok and bad == 0
