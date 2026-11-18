#  Franco De Escondrillas ft. Claude Code · 2026-11-09
"""Top-down render of the exported OBJ (re-parsed) + lane graph, for verification."""
import json, sys
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.collections import PolyCollection

obj, mtl, graph, out = sys.argv[1:5]
kd, cur = {}, None
for ln in open(mtl):
    if ln.startswith("newmtl"): cur = ln.split()[1]
    if ln.startswith("Kd"): kd[cur] = tuple(map(float, ln.split()[1:]))
V, groups, g = [], {}, None
for ln in open(obj):
    if ln.startswith("v "): V.append(list(map(float, ln.split()[1:4])))
    elif ln.startswith("usemtl"): g = ln.split()[1]; groups[g] = []
    elif ln.startswith("f "): groups[g].append([int(t.split("/")[0]) - 1 for t in ln.split()[1:]])
V = np.array(V)
print({k: len(v) for k, v in groups.items()}, "bbox", V.min(0).round(1), V.max(0).round(1))
lanes = json.load(open(graph))["lanes"]
for name, (xl, yl, dpi, show) in {"full": ((-370, 370), (-240, 240), 110, False),
                                  "etoile": ((-110, 110), (-75, 75), 160, True)}.items():
    fig, ax = plt.subplots(figsize=(18, 12)); ax.set_facecolor("k")
    for k in ["ground", "roads", "parks", "buildings", "markings_white", "markings_yellow"]:
        f = np.array(groups[k]); t = V[f][:, :, [0, 2]] * [1, -1]
        ax.add_collection(PolyCollection(t, facecolors=kd[k], edgecolors="none", antialiased=False))
    if show:
        for l in lanes:
            p = np.array(l["points"]); ax.plot(p[:, 0], -p[:, 2], "-", lw=0.6, color="c" if l["direction"] == "forward" else "m", alpha=0.7)
    ax.set_xlim(*xl); ax.set_ylim(*yl); ax.set_aspect("equal")
    fig.savefig(out.replace(".png", f"_{name}.png"), dpi=dpi, bbox_inches="tight"); plt.close(fig)
