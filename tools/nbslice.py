import sys, json
nb = json.load(open(sys.argv[1])); a, b = int(sys.argv[2]), int(sys.argv[3])
MAXL = int(sys.argv[4]) if len(sys.argv) > 4 else 25
for i, c in enumerate(nb["cells"][a:b+1], start=a):
    src = "".join(c["source"]).rstrip()
    if c["cell_type"] == "markdown":
        print(f"\n<!-- cell {i} markdown -->\n{src}")
        continue
    print(f"\n<!-- cell {i} code -->\n```python\n{src}\n```")
    for o in c.get("outputs", []):
        t = o.get("output_type")
        if t == "stream":
            txt = "".join(o.get("text", ""))
        elif t in ("execute_result", "display_data"):
            d = o.get("data", {})
            if "text/plain" in d: txt = "".join(d["text/plain"])
            else: txt = f"[{', '.join(k for k in d)} omitted]"
        elif t == "error":
            txt = f"{o.get('ename')}: {o.get('evalue')}"
        else:
            txt = f"[{t}]"
        lines = txt.splitlines()
        shown = "\n".join(lines[:MAXL])
        more = f"\n... [{len(lines)-MAXL} more lines truncated]" if len(lines) > MAXL else ""
        print(f"```text\n{shown}{more}\n```")
