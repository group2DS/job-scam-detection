import sys, json
nb = json.load(open(sys.argv[1]))
for i, c in enumerate(nb["cells"]):
    src = "".join(c["source"]).strip().splitlines()
    head = src[0][:95] if src else "<empty>"
    outs = c.get("outputs", [])
    nbytes = len(json.dumps(outs))
    print(f"{i:4d} | {c['cell_type'][:8]:8} | out={len(outs):2d} {nbytes//1024:5d}KB | {head}")
