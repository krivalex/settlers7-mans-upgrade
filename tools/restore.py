"""Restore the original Interface.bba from the .orig backup."""
import os, shutil, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import gamepath

if __name__ == "__main__":
    plain = [a for a in sys.argv[1:] if not a.startswith("--")]
    target = plain[0] if plain else gamepath.interface_bba()
    bak = target + ".orig"
    if not os.path.exists(bak):
        sys.exit("no backup found: %s" % bak)
    shutil.copy2(bak, target)
    print("restored %s from %s" % (target, bak))
