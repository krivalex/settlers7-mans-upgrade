"""Build the S7 mod: always starts from the pristine Interface.bba.orig,
applies every patch below, and writes Interface.bba.

Usage:
    python build_mod.py                      # find the game and patch it
    python build_mod.py --game "D:\...\The Settlers 7 - History Edition"
    python build_mod.py test.bba             # dry run into a scratch copy
"""
import os, shutil, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from bba import BBA
import bbapatch

import gamepath
HERE = os.path.dirname(os.path.abspath(__file__))
GAME = gamepath.interface_bba()
SETTLERS = "Script\\profiles\\settlers.lua"

# ---------------------------------------------------------------- settings --
ARMY_SIZE = 100          # was 35
CARRIER_SPEED_MULT = 5   # base velocity 0.4 -> 2.0

# settlers.lua has 186 constants; a numeric literal is stored as
#   descriptor = value + (#constants % 256) + 555
SETTLERS_CONSTS = 186


def const(value, n=SETTLERS_CONSTS):
    return value + (n % 256) + 555


def patch_army_size(src):
    """setGeneralDefaults -> SetArmySize(35) becomes ARMY_SIZE."""
    old, new = "{%d}" % const(35), "{%d}" % const(ARMY_SIZE)
    if src.count(old) != 1:
        raise AssertionError("expected exactly one %s, found %d" % (old, src.count(old)))
    return src.replace(old, new)


def patch_carrier_speed(src):
    """Carriers share setDefaultSpeed with all 29 worker types, so the shared
    constant cannot be touched. Override just the carrier profile instead."""
    base = 0.4 * CARRIER_SPEED_MULT
    return src + (
        "\n-- S7Mod: carriers %gx faster (base velocity 0.4 -> %g)\n"
        "settlerIDs.Carrier:SetBaseVelocity(%g)\n" % (CARRIER_SPEED_MULT, base, base)
    )


PATCHES = {SETTLERS: [patch_army_size, patch_carrier_speed]}
# ---------------------------------------------------------------------------


def build(dst):
    orig = GAME + ".orig"
    if not os.path.exists(orig):
        if dst == GAME:
            shutil.copy2(GAME, orig)
            print("[backup] %s" % orig)
        else:
            orig = GAME
    if os.path.abspath(dst) != os.path.abspath(orig):
        shutil.copy2(orig, dst)

    a = BBA(orig)
    by_name = {e.name: e for e in a.entries}
    new_content = {}
    for name, fns in PATCHES.items():
        data = a.read(by_name[name]).decode("utf-8", "surrogateescape")
        before = len(data)
        for fn in fns:
            data = fn(data)
            print("  applied %-22s -> %d bytes" % (fn.__name__, len(data)))
        new_content[name] = data.encode("utf-8", "surrogateescape")
        print("%s: %d -> %d bytes" % (name, before, len(new_content[name])))
    a.f.close()

    bbapatch.patch(dst, new_content, backup=False)
    print("-" * 55)
    ok = bbapatch.verify(dst, new_content)
    print("[result]", "OK" if ok else "PROBLEMS FOUND")
    return ok


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if "--game" in sys.argv:
        i = sys.argv.index("--game")
        args = [a for a in args if a != sys.argv[i + 1]] if i + 1 < len(sys.argv) else args
    dst = args[0] if args else GAME
    print("[game] %s" % GAME)
    sys.exit(0 if build(dst) else 1)
