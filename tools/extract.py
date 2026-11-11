import sys, os
from bba import BBA
a = BBA(sys.argv[1]); out = sys.argv[2]
n=0; err=0
for e in a.entries:
    if e.ftype == 256 or e.name in (".",""): continue
    p = os.path.join(out, e.name.replace("\\", os.sep))
    os.makedirs(os.path.dirname(p), exist_ok=True)
    try:
        d = a.read(e)
        open(p,"wb").write(d); n+=1
    except Exception as ex:
        err+=1; print("ERR", e.name, ex)
print("extracted", n, "errors", err)
