import sys, json
nb = json.load(sys.stdin)
for i, c in enumerate(nb["cells"]):
    print(f"--- cell {i} [{c['cell_type']}] ---")
    print("".join(c["source"]).rstrip())
