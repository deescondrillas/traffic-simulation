#  Franco De Escondrillas ft. Claude Code · 2026-11-09
"""Independent QA of lane markings, read back from the exported OBJ.

usage: check_markings.py <obj> <out_png> [lane_w=2.7] [dash=3.0] [gap=5.0] [line_w=0.15]

Each marking is a connected triangle group. Checks:
  size       every white dash is dash x line_w (PCA extents)
  continuity every dash has a neighbour one period (dash+gap) ahead or behind on the same line
  spacing    nearest side-by-side line is a whole number of lane widths away
  parallel   side-by-side dashes share the same heading
  crossing   no white touches yellow, no marking is wider than a single stripe
Flagged markings are drawn red on the output image.
"""
import sys

import numpy as np
import shapely
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import connected_components
from scipy.spatial import cKDTree

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.collections import PolyCollection

obj, out_png = sys.argv[1:3]
LANE_W, DASH, GAP, LINE_W = (list(map(float, sys.argv[3:7])) + [2.7, 3.0, 5.0, 0.15][len(sys.argv[3:7]):])
PERIOD = DASH + GAP

V, groups, g = [], {}, None
for ln in open(obj):
    if ln.startswith("v "):
        V.append(list(map(float, ln.split()[1:4])))
    elif ln.startswith("o "):
        g = ln.split()[1]; groups[g] = []
    elif ln.startswith("f "):
        groups[g].append([int(t.split("/")[0]) - 1 for t in ln.split()[1:]])
V = np.array(V)
P = np.c_[V[:, 0], -V[:, 2]]  # east, north


def components(faces):
    f = np.array(faces)
    if len(f) == 0:
        return []
    e = np.r_[f[:, [0, 1]], f[:, [1, 2]]]
    n = V.shape[0]
    _, lab = connected_components(coo_matrix((np.ones(len(e)), (e[:, 0], e[:, 1])), shape=(n, n)), directed=False)
    flab = lab[f[:, 0]]
    out = []
    for k in np.unique(flab):
        ff = f[flab == k]
        pts = P[np.unique(ff)]
        tri = P[ff]
        e1, e2 = tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0]
        ta = 0.5 * np.abs(e1[:, 0] * e2[:, 1] - e1[:, 1] * e2[:, 0])
        c = (tri.mean(1) * ta[:, None]).sum(0) / max(ta.sum(), 1e-12)  # area centroid, not vertex mean
        w, vec = np.linalg.eigh(np.cov((pts - c).T))
        ax = vec[:, 1]
        a = (pts - c) @ ax
        b = (pts - c) @ vec[:, 0]
        area = ta.sum()
        out.append({"c": c, "ax": ax, "len": np.ptp(a), "wid": np.ptp(b), "area": area, "tris": tri})
    return out


white = components(groups["markings_white"])
yellow = components(groups["markings_yellow"])
dash = [m for m in white if m["len"] < DASH * 1.6]
solid_white = [m for m in white if m["len"] >= DASH * 1.6]
flag = set()

# size
L = np.array([m["len"] for m in dash]); Wd = np.array([m["area"] / max(m["len"], 1e-6) for m in dash])
bad_size = np.flatnonzero((np.abs(L - DASH) > 0.1) | (np.abs(Wd - LINE_W) > 0.03))
flag |= {("w", i) for i in bad_size}

# continuity / spacing / parallel
C = np.array([m["c"] for m in dash]); A = np.array([m["ax"] for m in dash])
tree = cKDTree(C)
isolated, spacing, bad_spacing, bad_par = [], [], [], []
for i, (c, ax) in enumerate(zip(C, A)):
    nrm = np.array([-ax[1], ax[0]])
    cont = False
    for j in tree.query_ball_point(c, PERIOD + 1.0):
        if j == i:
            continue
        d = C[j] - c
        along, lat = d @ ax, d @ nrm
        # curve-safe: one period away (chord), roughly ahead/behind, same heading within 15 deg
        if abs(np.linalg.norm(d) - PERIOD) < 0.35 and abs(along) > 0.9 * PERIOD and abs(lat) < 1.2 \
                and abs(A[j] @ ax) > np.cos(np.radians(15)):
            cont = True
    if not cont:
        isolated.append(i)
    lats = []
    for j in tree.query_ball_point(c, 4 * LANE_W):
        d = C[j] - c
        if j != i and abs(d @ ax) < 1.0 and abs(d @ nrm) > 0.5:
            lats.append((abs(d @ nrm), j))
    if lats:
        dist, j = min(lats)
        spacing.append(dist)
        k = round(dist / LANE_W)
        if k == 0 or abs(dist - k * LANE_W) > 0.1:
            bad_spacing.append(i)
        if abs(A[j] @ ax) < np.cos(np.radians(3)):
            bad_par.append(i)
flag |= {("w", i) for i in isolated + bad_spacing + bad_par}

# crossings
wpolys = [shapely.union_all([shapely.Polygon(t) for t in m["tris"]]) for m in white]
ypolys = [shapely.union_all([shapely.Polygon(t) for t in m["tris"]]) for m in yellow]
ytree = shapely.STRtree(ypolys) if ypolys else None
cross = [i for i, p in enumerate(wpolys) if ytree is not None and len(ytree.query(p.buffer(0.02), "intersects"))]
too_wide = [i for i, m in enumerate(white) if m["area"] / max(m["len"], 1e-6) > LINE_W * 1.5]
y_wide = [i for i, m in enumerate(yellow) if m["area"] / max(m["len"], 1e-6) > LINE_W * 1.5]
wid = {id(m): k for k, m in enumerate(dash)}
flag |= {("W", i) for i in cross + too_wide} | {("y", i) for i in y_wide}

print(f"white components {len(white)} (dashes {len(dash)}, long/solid {len(solid_white)}), yellow {len(yellow)}")
print(f"dash length  mean {L.mean():.3f}  min {L.min():.3f}  max {L.max():.3f}  off-size {len(bad_size)}")
print(f"dash width   mean {Wd.mean():.3f}  min {Wd.min():.3f}  max {Wd.max():.3f}")
print(f"isolated dashes (no neighbour one period ahead/behind) {len(isolated)} ({100 * len(isolated) / len(dash):.1f}%)")
sp = np.array(spacing)
print(f"lateral spacing to nearest line: median {np.median(sp):.3f}, off-grid (>0.1 m from k*{LANE_W}) {len(bad_spacing)}")
print(f"non-parallel neighbours (>3 deg) {len(bad_par)}")
print(f"white touching yellow {len(cross)}, white wider than a stripe {len(too_wide)}, yellow wider than a stripe {len(y_wide)}")
ylen = np.array([m["len"] for m in yellow]) if yellow else np.zeros(1)
print(f"yellow pieces: {len(yellow)}, shorter than 10 m: {(ylen < 10).sum()}")

fig, ax = plt.subplots(figsize=(18, 12)); ax.set_facecolor("#333")
for kind, lst, col in (("w", dash, "w"), ("W", white, "w"), ("y", yellow, "#f2be1a")):
    ok = [m["tris"] for k, m in enumerate(lst) if (kind, k) not in flag]
    ax.add_collection(PolyCollection([t for tt in ok for t in tt], facecolors=col, edgecolors="none"))
bad = [m["tris"] for k, m in enumerate(dash) if ("w", k) in flag] + \
      [m["tris"] for k, m in enumerate(white) if ("W", k) in flag] + \
      [m["tris"] for k, m in enumerate(yellow) if ("y", k) in flag]
ax.add_collection(PolyCollection([t for tt in bad for t in tt], facecolors="r", edgecolors="r", linewidths=1.5))
for m in [m for k, m in enumerate(dash) if ("w", k) in flag]:
    ax.plot(*m["c"], "o", ms=6, mfc="none", mec="r")
ax.set_aspect("equal")
for name, (xl, yl) in {"": ((-370, 370), (-240, 240)), "_zoom": ((-95, 95), (-80, 80))}.items():
    ax.set_xlim(*xl); ax.set_ylim(*yl)
    fig.savefig(out_png.replace(".png", f"{name}.png"), dpi=110, bbox_inches="tight")
print("flagged", len(flag))
