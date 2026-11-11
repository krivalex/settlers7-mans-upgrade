"""Locate MSVC RTTI class vftables and their constructors in the S7 exe."""
import os, re, struct, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pefile, capstone

import gamepath
EXE = os.environ.get("S7_EXE") or os.path.join(
    gamepath.game_root(), "Data", "Base", "Bin", "Settlers7R.exe.unpacked.exe")

pe = pefile.PE(EXE, fast_load=True)
BASE = pe.OPTIONAL_HEADER.ImageBase
IS64 = pe.FILE_HEADER.Machine == 0x8664
data = pe.__data__


def secs():
    out = []
    for s in pe.sections:
        out.append((s.Name.rstrip(b"\0").decode(), s.VirtualAddress + BASE,
                    s.Misc_VirtualSize, s.PointerToRawData, s.SizeOfRawData))
    return out


SECTIONS = secs()


def va2off(va):
    for n, v, vs, po, rs in SECTIONS:
        if v <= va < v + max(vs, rs):
            o = va - v + po
            if o < len(data):
                return o
    return None


def off2va(off):
    for n, v, vs, po, rs in SECTIONS:
        if po <= off < po + rs:
            return off - po + v
    return None


def find_all(needle, blob=None):
    blob = data if blob is None else blob
    out, i = [], blob.find(needle)
    while i >= 0:
        out.append(i)
        i = blob.find(needle, i + 1)
    return out


def find_class(name):
    """name like '.?AVCProfileCarrier@ED@@' -> (td_va, [vftable_va,...])"""
    res = []
    for off in find_all(name.encode() + b"\0"):
        td_off = off - 8          # TypeDescriptor: vfptr, spare, name
        td_va = off2va(td_off)
        if td_va is None:
            continue
        # find COL referencing this TD
        for colref in find_all(struct.pack("<I", td_va)):
            col_va = off2va(colref - 12)   # pTypeDescriptor is field #3
            if col_va is None:
                continue
            # vftable = address right after a pointer to the COL
            for vfref in find_all(struct.pack("<I", col_va)):
                vf_va = off2va(vfref + 4)
                if vf_va:
                    res.append((td_va, col_va, vf_va))
    return res


def disasm_at(va, count=60):
    off = va2off(va)
    md = capstone.Cs(capstone.CS_ARCH_X86,
                     capstone.CS_MODE_64 if IS64 else capstone.CS_MODE_32)
    md.detail = False
    out = []
    for i in md.disasm(data[off:off + count * 8], va):
        out.append("%08x  %-22s %s %s" % (i.address, i.bytes.hex(), i.mnemonic, i.op_str))
        if len(out) >= count:
            break
    return out


if __name__ == "__main__":
    print("64-bit" if IS64 else "32-bit", "base=0x%x" % BASE)
    for n, v, vs, po, rs in SECTIONS:
        print("  %-10s va=0x%08x vsize=0x%-8x raw=0x%08x" % (n, v, vs, po))
    for cls in sys.argv[1:]:
        print("\n=== %s ===" % cls)
        for td, col, vf in find_class(cls):
            print("  TD=0x%08x COL=0x%08x VFTABLE=0x%08x" % (td, col, vf))
