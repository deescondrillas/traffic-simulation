#  Franco De Escondrillas ft. Claude Code · 2026-11-09
"""Are the painted lines parallel to the asphalt edges? Read back from the exported OBJ.

usage: check_parallel.py <obj> <out_png> [max_deg=0.3]

Lines = dash chains (one period apart, same heading) and yellow pieces. Along each line, rays
are cast sideways to the road-surface boundary; the distance to the left and right edge should
stay constant. The trend of that distance (Theil-Sen slope, robust to side-street openings)
is the angle between the line and the edge.
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
MAX_DEG = float(sys.argv[3]) if len(sys.argv) > 3 else 0.3
PERIOD = 8.0

V, G, g = [], {}, None
for ln in open(obj):
    if ln.startswith("v "):
        V.append(list(map(float, ln.split()[1:4])))
    elif ln.startswith("o "):
        g = ln.split()[1]; G[g] = []
    elif ln.startswith("f "):
        G[g].append([int(t.split("/")[0]) - 1 for t in ln.split()[1:]])
V = np.array(V); P = np.c_[V[:, 0], -V[:, 2]]

road_tris = P[np.array(G["roads"])]
road = shapely.union_all([shapely.Polygon(t) for t in road_tris if shapely.Polygon(t).area > 1e-6])
edge = road.boundary
shapely.prepare(edge)


def components(faces):
    f = np.array(faces)
    e = np.r_[f[:, [0, 1]], f[:, [1, 2]]]
    n = len(V)
    _, lab = connected_components(coo_matrix((np.ones(len(e)), (e[:, 0], e[:, 1])), shape=(n, n)), directed=False)
    out = []
    for k in np.unique(lab[f[:, 0]]):
        tri = P[f[lab[f[:, 0]] == k]]
        e1, e2 = tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0]
        a = 0.5 * np.abs(e1[:, 0] * e2[:, 1] - e1[:, 1] * e2[:, 0])
        pts = tri.reshape(-1, 2)
        c = (tri.mean(1) * a[:, None]).sum(0) / a.sum()
        vec = np.linalg.eigh(np.cov((pts - c).T))[1]
        out.append({"c": c, "ax": vec[:, 1], "tris": tri, "pts": pts})
    return out


white, yellow = components(G["markings_white"]), components(G["markings_yellow"])
C = np.array([m["c"] for m in white]); A = np.array([m["ax"] for m in white])
pairs = []
for i, j in cKDTree(C).query_pairs(PERIOD + 0.5):
    d = C[j] - C[i]
    lat = abs(d @ np.array([-A[i][1], A[i][0]]))
    if abs(np.linalg.norm(d) - PERIOD) < 0.35 and abs(A[i] @ A[j]) > np.cos(np.radians(15)) \
            and abs(d @ A[i]) > 0.9 * PERIOD and lat < 1.5:
        pairs.append((i, j))
pairs = np.array(pairs)
_, lab = connected_components(coo_matrix((np.ones(len(pairs)), (pairs[:, 0], pairs[:, 1])),
                                         shape=(len(C), len(C))), directed=False)

lines = []
for k in np.unique(lab):
    ids = np.flatnonzero(lab == k)
    if len(ids) >= 4:
        lines.append({"samples": C[ids], "tris": [white[i]["tris"] for i in ids], "kind": "white"})
for m in yellow:
    L = np.ptp((m["pts"] - m["c"]) @ m["ax"])
    if L >= 20:
        t = np.linspace(-L / 2 + 1, L / 2 - 1, max(4, int(L / 4)))
        lines.append({"samples": m["c"] + t[:, None] * m["ax"], "tris": [m["tris"]], "kind": "yellow"})


def side_dist(p, nrm, sgn, reach=20.0):
    hit = shapely.LineString([p, p + sgn * nrm * reach]).intersection(edge)
    if hit.is_empty:
        return np.nan
    return shapely.Point(p).distance(hit)


def theil_sen(s, d):
    ok = ~np.isnan(d)
    s, d = s[ok], d[ok]
    if len(s) < 4:
        return np.nan
    i, j = np.triu_indices(len(s), 1)
    keep = np.abs(s[j] - s[i]) > 4
    return np.median((d[j] - d[i])[keep] / (s[j] - s[i])[keep]) if keep.any() else np.nan


bad = []
angles = []
for L in lines:
    S = L["samples"]
    c = S.mean(0)
    ax = np.linalg.eigh(np.cov((S - c).T))[1][:, 1]
    if len(S) < 3 or np.linalg.norm(S - c, axis=1).max() < 10:
        continue
    nrm = np.array([-ax[1], ax[0]])
    # skip ring lines (curved): straightness of samples
    if np.abs((S - c) @ nrm).max() > 1.0:
        continue
    s = (S - c) @ ax
    dl = np.array([side_dist(p, nrm, 1) for p in S])
    dr = np.array([side_dist(p, nrm, -1) for p in S])
    width = dl + dr
    wmed = np.nanmedian(width)
    junk = np.abs(width - wmed) > 0.5  # side-street openings / road joins
    dl[junk] = np.nan; dr[junk] = np.nan
    sl, sr = theil_sen(s, dl), theil_sen(s, dr)
    if np.isnan(sl) and np.isnan(sr):
        continue
    ang = np.degrees(np.arctan(np.nanmean([sl, -sr])))  # left edge recedes as right approaches
    L.update(angle=ang, centre=c, span=np.ptp(s))
    angles.append(abs(ang))
    if abs(ang) > MAX_DEG:
        bad.append(L)

angles = np.array(angles)
print(f"straight lines measured: {len(angles)}; angle to asphalt edge median {np.median(angles):.3f} deg, "
      f"max {angles.max():.3f} deg; over {MAX_DEG} deg: {len(bad)}")
for L in sorted(bad, key=lambda L: -abs(L["angle"])):
    x, y = L["centre"]
    print(f"  {L['kind']:6s} line at ({x:7.1f}, {y:7.1f}) span {L['span']:5.0f} m: {L['angle']:+.2f} deg "
          f"(drift {np.tan(np.radians(abs(L['angle']))) * L['span']:.2f} m over its length)")

fig, ax = plt.subplots(figsize=(18, 12)); ax.set_facecolor("k")
ax.add_collection(PolyCollection(list(road_tris), facecolors="#555", edgecolors="none"))
ax.add_collection(PolyCollection([t for L in lines for tt in L["tris"] for t in tt], facecolors="w", edgecolors="none"))
ax.add_collection(PolyCollection([t for L in bad for tt in L["tris"] for t in tt], facecolors="r", edgecolors="r", lw=2))
for L in bad:
    ax.annotate(f"{L['angle']:+.1f}°", L["centre"], color="r", fontsize=11, xytext=(8, 8), textcoords="offset points")
ax.set_xlim(-370, 370); ax.set_ylim(-240, 240); ax.set_aspect("equal")
fig.savefig(out_png, dpi=110, bbox_inches="tight")
