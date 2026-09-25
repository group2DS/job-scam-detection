import sys, json
nb = json.load(open(sys.argv[1]))
seq, prev, bad = [], 0, []
for i, c in enumerate(nb["cells"]):
    if c["cell_type"] != "code": continue
    n = c.get("execution_count")
    seq.append((i, n))
    if n is None: bad.append((i, "NOT RUN"))
    elif n <= prev: bad.append((i, f"out of order: {n} after {prev}"))
    else:
        if n != prev + 1: bad.append((i, f"gap: {prev} -> {n}"))
        prev = n
print(f"code cells: {len(seq)}  max exec count: {prev}")
print("VERDICT:", "clean sequential run" if not bad else f"{len(bad)} anomalies")
for i, why in bad: print(f"  cell {i:4d}: {why}")
