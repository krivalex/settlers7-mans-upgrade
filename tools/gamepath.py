"""Locate the Settlers 7 - History Edition install directory.

Resolution order:
  1. --game <path> on the command line
  2. S7_GAME environment variable
  3. the repo sitting inside the game folder (<game>/<repo>/tools/)
  4. common Steam library locations on every local drive
"""
import os, sys, string

MARKER = os.path.join("Data", "Base", "BBA", "Interface.bba")
HERE = os.path.dirname(os.path.abspath(__file__))


def _ok(root):
    return root and os.path.isfile(os.path.join(root, MARKER))


def _from_argv():
    if "--game" in sys.argv:
        i = sys.argv.index("--game")
        if i + 1 < len(sys.argv):
            return sys.argv[i + 1]
    return None


def _steam_guesses():
    rel = os.path.join("steamapps", "common", "The Settlers 7 - History Edition")
    out = []
    for d in string.ascii_uppercase:
        for base in ("Program Files (x86)\Steam", "Steam", "Games\Steam", "SteamLibrary", "GAMES"):
            out.append(os.path.join(d + ":\\", base, rel))
    out.append(os.path.expanduser("~/.steam/steam/" + rel.replace("\\", "/")))
    return out


def game_root():
    for cand in (_from_argv(), os.environ.get("S7_GAME"),
                 os.path.abspath(os.path.join(HERE, "..", "..")),
                 *_steam_guesses()):
        if _ok(cand):
            return os.path.abspath(cand)
    sys.exit(
        "Could not find the game.\n"
        "Pass it explicitly:  python build_mod.py --game \"D:\Steam\steamapps\common\The Settlers 7 - History Edition\"\n"
        "or set the S7_GAME environment variable.")


def interface_bba():
    return os.path.join(game_root(), MARKER)
