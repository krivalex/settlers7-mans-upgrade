import os, sys, traceback
from deobf import deobfuscate
src_root, dst_root = sys.argv[1], sys.argv[2]
n=ok=0
for dp,_,fs in os.walk(src_root):
    for f in fs:
        if not f.endswith(".lua"): continue
        p=os.path.join(dp,f); n+=1
        rel=os.path.relpath(p,src_root)
        out=os.path.join(dst_root,rel)
        os.makedirs(os.path.dirname(out),exist_ok=True)
        try:
            s=open(p,encoding="utf-8",errors="replace").read()
            b,c=deobfuscate(s)
            open(out,"w",encoding="utf-8").write(b if b else s); ok+=1
        except Exception as e:
            open(out,"w",encoding="utf-8").write(s)
print("processed %d/%d"%(ok,n))
