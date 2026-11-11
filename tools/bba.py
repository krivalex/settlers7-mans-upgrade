"""BBA (Settlers 7) archive reader — Python port of Eisenmonoxid/S7Packer."""
import struct, sys, os, gzip, io, zlib

M = 0xFFFFFFFF
ONE_MIB = 1048576

PROD_HEAD_DELTA = 1231853475
PROD_HEAD_LOOP  = 7
PROD_FILE_DELTA = 1532281822
PROD_FILE_LOOP  = 8
PROD_XOR = [68040748, 166934560, 1719695735, 4247314248]

HEAD_KEYS = [623092400, 3578011951, 428883204, 211416760]
FILE_KEYS = [892421091, 3702197895, 3064602941, 189782668]

HEADER_START_OFFSET = 69   # uints
HEADER_SIZE = 16           # bytes


def feistel(y, z, s, k):
    return (((y >> 5) ^ ((z << 2) & M)) + (((y << 4) & M) ^ (z >> 3))) ^ ((s ^ z) + (k ^ y)) & M


def decrypt(v, keys, delta, loops):
    """XXTEA-style decryption, in place on list of uint32."""
    n = len(v)
    s = (loops * delta) & M
    while s != 0:
        e = (s >> 2) & 3
        z = v[0]
        for p in range(n - 1, 0, -1):
            y = v[p - 1]
            v[p] = (v[p] - feistel(y, z, s, keys[(p & 3) ^ e])) & M
            z = v[p]
        y = v[n - 1]
        v[0] = (v[0] - ((((y >> 5) ^ ((z << 2) & M)) + (((y << 4) & M) ^ (z >> 3))) ^ ((s ^ z) + (keys[e] ^ y)))) & M
        s = (s - delta) & M
    return v


def encrypt(v, keys, delta, loops):
    n = len(v)
    s = 0
    end = (loops * delta) & M
    while s != end:
        s = (s + delta) & M
        e = (s >> 2) & 3
        y = v[n - 1]
        for p in range(0, n - 1):
            z = v[p + 1]
            v[p] = (v[p] + feistel(y, z, s, keys[(p & 3) ^ e])) & M
            y = v[p]
        z = v[0]
        v[n - 1] = (v[n - 1] + (((((y >> 5) ^ ((z << 2) & M)) + (((y << 4) & M) ^ (z >> 3))) ^ ((s ^ z) + (keys[((n - 1) & 3) ^ e] ^ y))))) & M
    return v


def to_u32(b):
    return list(struct.unpack("<%dI" % (len(b) // 4), b[:len(b) // 4 * 4]))


def from_u32(v):
    return struct.pack("<%dI" % len(v), *v)


def decrypt_compressed(chunk, name_len, xor=PROD_XOR):
    """XOR-decrypt first 16 bytes of a compressed chunk."""
    i = to_u32(chunk[:16])
    i[3] ^= i[2] ^ name_len ^ xor[3]
    i[2] ^= i[1] ^ name_len ^ xor[2]
    i[1] ^= i[0] ^ name_len ^ xor[1]
    i[0] ^= i[3] ^ name_len ^ xor[0]
    return from_u32([x & M for x in i]) + chunk[16:]


def encrypt_compressed(chunk, name_len, xor=PROD_XOR):
    i = to_u32(chunk[:16])
    i[0] ^= i[3] ^ name_len ^ xor[0]
    i[1] ^= i[0] ^ name_len ^ xor[1]
    i[2] ^= i[1] ^ name_len ^ xor[2]
    i[3] ^= i[2] ^ name_len ^ xor[3]
    return from_u32([x & M for x in i]) + chunk[16:]


def handle_tea(data, name_len, block_size, delta, loops, do_encrypt=False):
    data = bytearray(data)
    n = len(data)
    off = 0
    while off < n:
        remaining = n - off
        copy_len = min(block_size, remaining)
        padder = (remaining + 3) & ~3
        padding = block_size if copy_len == block_size else padder
        buf = bytearray(padding)
        buf[:copy_len] = data[off:off + copy_len]
        v = to_u32(bytes(buf))
        if len(v) >= 2:
            (encrypt if do_encrypt else decrypt)(v, FILE_KEYS_for(name_len), delta, loops)
            out = from_u32(v)
            data[off:off + copy_len] = out[:copy_len]
        off += block_size
    return bytes(data)


def FILE_KEYS_for(name_len):
    return [(892421091 ^ name_len) & M, (3702197895 ^ name_len) & M,
            (3064602941 ^ name_len) & M, (189782668 ^ name_len) & M]


class Entry:
    __slots__ = ("name", "dec_size", "dec_crc", "ftype", "offset",
                 "comp_size", "comp_crc", "block_size", "name_len", "raw_off")

    def __repr__(self):
        return "<%s type=%d size=%d comp=%d off=%d>" % (
            self.name, self.ftype, self.dec_size, self.comp_size, self.offset)


class BBA:
    def __init__(self, path):
        self.path = path
        self.f = open(path, "rb")
        head = self.f.read(HEADER_SIZE)
        assert head[:3] == b"BAF", "not a BBA file"
        self.version = head[3]
        self.header_size = struct.unpack_from("<I", head, 8)[0]

        hb = to_u32(self.f.read(self.header_size))
        decrypt(hb, HEAD_KEYS, PROD_HEAD_DELTA, PROD_HEAD_LOOP)
        self.dir_offset = hb[0]
        self.dir_length = hb[2] if hb[2] != 0 else 16
        self.dir_crc = hb[3]

        self.f.seek(self.dir_offset)
        db = to_u32(self.f.read(self.dir_length))
        decrypt(db, FILE_KEYS, PROD_FILE_DELTA, PROD_FILE_LOOP)
        self.dirblob = db

        self.offset_hashtable = db[2]
        self.num_files = db[68]
        self.entries = self._parse_entries()

    def _parse_entries(self):
        d = self.dirblob
        i = HEADER_START_OFFSET
        out = []
        while i + 16 <= len(d):
            name_len = d[i + 12]
            if name_len == 0:
                break
            e = Entry()
            e.raw_off = i * 4
            e.dec_size = d[i + 2]
            e.dec_crc = d[i + 3]
            e.ftype = d[i + 4]
            e.offset = d[i + 6]
            e.comp_size = d[i + 8]
            e.comp_crc = d[i + 9]
            e.block_size = d[i + 10]
            e.name_len = name_len
            nb = from_u32(d[i + 16:i + 16 + (name_len + 7) // 4 + 1])
            e.name = nb[:name_len].decode("ascii", "replace").rstrip("\0")
            out.append(e)
            pad = ((name_len + 3) & ~3) + (4 if name_len % 4 == 0 else 0)
            i += 16 + pad // 4
        return out

    def read(self, e):
        """Return decompressed/decrypted bytes for entry e."""
        if e.ftype == 256:
            return None  # directory
        self.f.seek(e.offset)
        src = self.f.read(e.comp_size)
        if e.ftype == 17:  # zlib/gzip compressed
            out = bytearray()
            for off in range(0, len(src), ONE_MIB):
                chunk = src[off:off + ONE_MIB]
                if len(chunk) >= 16:
                    chunk = decrypt_compressed(chunk, e.name_len)
                out += chunk
            return gzip.GzipFile(fileobj=io.BytesIO(bytes(out))).read()
        elif e.ftype == 2:  # TEA
            return handle_tea(src, e.name_len, e.block_size or ONE_MIB,
                              PROD_FILE_DELTA, PROD_FILE_LOOP, False)
        else:
            return src


if __name__ == "__main__":
    a = BBA(sys.argv[1])
    print("version=%d files=%d dir_off=%d dir_len=%d" % (
        a.version, a.num_files, a.dir_offset, a.dir_length))
    for e in a.entries:
        print("%-70s type=%-4d size=%-10d comp=%-10d" % (e.name, e.ftype, e.dec_size, e.comp_size))
