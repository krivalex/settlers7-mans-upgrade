import re,sys
d=open(sys.argv[1],"rb").read()
pat=re.compile(rb"[\x20-\x7e]{%d,}"%int(sys.argv[2] if len(sys.argv)>2 else 5))
out=set()
for m in pat.finditer(d): out.add(m.group().decode("ascii"))
for s in sorted(out): print(s)
