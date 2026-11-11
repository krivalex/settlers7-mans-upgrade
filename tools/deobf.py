"""Deobfuscate Settlers 7 profile Lua files.

The obfuscator replaces every literal with a call `f(index)` into a lazily
decoded constant table `o`:
  * number: value = o[i][1] - (#o % 256) - 555          (single element, >= 555)
  * string: running-delta decode, seed = (#o % 256)
"""
import re, sys, os, io


def find_table(src):
    """Locate the `{{...}}` constant table and return (start, end, text)."""
    i = src.find("{{")
    if i < 0:
        return None
    depth = 0
    for j in range(i, len(src)):
        if src[j] == "{":
            depth += 1
        elif src[j] == "}":
            depth -= 1
            if depth == 0:
                return i, j + 1, src[i:j + 1]
    return None


def parse_table(text):
    """Parse `{{1,2},{3},...}` into a list of lists of numbers."""
    inner = text[1:-1]
    out = []
    for m in re.finditer(r"\{([^{}]*)\}", inner):
        body = m.group(1).strip()
        if not body:
            out.append([])
            continue
        out.append([float(x) if "." in x else int(x)
                    for x in body.split(",") if x.strip()])
    return out


def decode(entries):
    d = len(entries) % 256
    consts = {}
    for idx, n in enumerate(entries, 1):
        if len(n) == 1 and n[0] >= 555:
            v = n[0] - d - 555
            # collapse float that is really an int
            if isinstance(v, float) and abs(v - round(v)) < 1e-9:
                v = int(round(v))
            consts[idx] = v
        else:
            c = d
            chars = []
            for e in n:
                e = int(e) - c
                chars.append(chr(e % 256))
                c = int(e)
            consts[idx] = "".join(chars)
    return consts


def lua_repr(v):
    if isinstance(v, str):
        if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", v):
            return '"%s"' % v
        return '"%s"' % v.replace("\\", "\\\\").replace('"', '\\"')
    return repr(v)


def deobfuscate(src):
    t = find_table(src)
    if not t:
        return None, None
    start, end, text = t
    entries = parse_table(text)
    consts = decode(entries)

    # accessor names:  A,B,C=function(x)return e[x]or i(x)end,function(...)
    m = re.search(r"(\w+),(\w+),(\w+)\s*=\s*function\((\w+)\)\s*return\s+\w+\[\w+\]\s*or\s+\w+\(\w+\)\s*end", src)
    const_fn = m.group(1) if m else None
    glob_fn = m.group(2) if m else None

    body = src[src.find("end", src.find("local o")):]
    # take everything after the decoder block: the last `end` of the do-block
    dm = re.search(r"\n(?=\w*\[?\w*\(?\d)", src)
    # simpler: body = everything after the final `end\n` that closes `do`
    idx = src.find("\nend\n", end)
    body = src[idx + 5:] if idx > 0 else src[end:]

    def sub_const(mo):
        k = int(mo.group(1))
        return lua_repr(consts[k]) if k in consts else mo.group(0)

    def sub_glob(mo):
        k = int(mo.group(1))
        return consts[k] if k in consts and isinstance(consts[k], str) else mo.group(0)

    if const_fn:
        body = re.sub(r"\b%s\((\d+)\)" % re.escape(const_fn), sub_const, body)
    if glob_fn:
        body = re.sub(r"\b%s\((\d+)\)" % re.escape(glob_fn), sub_glob, body)

    # _G["Name"] -> Name ; ["Name"] -> .Name  for readability
    body = re.sub(r'\[\s*"([A-Za-z_][A-Za-z0-9_]*)"\s*\]', r".\1", body)
    # escaped-decimal strings "\116\097..." -> readable
    def unesc(mo):
        s = mo.group(1)
        if re.fullmatch(r"(\\\d{1,3})+", s):
            return '"%s"' % "".join(chr(int(x)) for x in re.findall(r"\\(\d{1,3})", s))
        return mo.group(0)
    body = re.sub(r'"((?:\\\d{1,3})+)"', unesc, body)

    # newline after each statement-ish boundary for readability
    body = re.sub(r"\)(?=[A-Za-z_])", ")\n", body)
    return body, consts


if __name__ == "__main__":
    src = open(sys.argv[1], "r", encoding="utf-8", errors="replace").read()
    body, consts = deobfuscate(src)
    if body is None:
        print("-- no constant table found; file may not be obfuscated")
        print(src)
    else:
        if "--consts" in sys.argv:
            for k in sorted(consts):
                print("%4d = %s" % (k, lua_repr(consts[k])))
            print("-" * 60)
        print(body)
