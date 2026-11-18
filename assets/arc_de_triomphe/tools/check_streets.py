#  Franco De Escondrillas ft. Claude Code · 2026-11-09
"""Street-level QA of markings, read back from the exported OBJ.

usage: check_streets.py <obj> <osm.json> <out_png>

  centre     Étoile centre = centre of the circle fitted to the ring dashes
  straight   each yellow piece: max deviation from its best-fit straight line
  radial     avenues meeting the ring: angle between the line and the ray from the centre
  oneway     no yellow on an OSM one-way street
  rows       per street near the ring: every lane line has the same dash count and
             the same gap from the ring's outer edge to the first dash
"""
import collections
import json
import sys

import numpy as np
import shapely
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import connected_components

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.collections import PolyCollection

from common import load_osm

obj, osm_path, out_png = sys.argv[1:4]
V, G, g = [], {}, None
for ln in open(obj):
    if ln.startswith("v "):
        V.append(list(map(float, ln.split()[1:4])))
    elif ln.startswith("o "):
        g = ln.split()[1]; G[g] = []
    elif ln.startswith("f "):
        G[g].append([int(t.split("/")[0]) - 1 for t in ln.split()[1:]])
V = np.array(V); P = np.c_[V[:, 0], -V[:, 2]]


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
        w, vec = np.linalg.eigh(np.cov((pts - c).T))
        out.append({"c": c, "ax": vec[:, 1], "tris": tri, "pts": pts,
                    "len": np.ptp((pts - c) @ vec[:, 1]),
                    "dev": np.abs((pts - c) @ vec[:, 0]).max() - 0.075})
    return out


white, yellow = components(G["markings_white"]), components(G["markings_yellow"])
PERIOD = 8.0

# 1. chain dashes into lane lines (one period apart, same heading)
C = np.array([m["c"] for m in white]); A = np.array([m["ax"] for m in white])
from scipy.spatial import cKDTree
tree = cKDTree(C)
pairs = []
for i, j in tree.query_pairs(PERIOD + 0.5):
    d = C[j] - C[i]
    lat = abs(d @ np.array([-A[i][1], A[i][0]]))  # same line only (neighbouring lanes are 2.7 m away)
    if abs(np.linalg.norm(d) - PERIOD) < 0.35 and abs(A[i] @ A[j]) > np.cos(np.radians(15)) \
            and abs(d @ A[i]) > 0.9 * PERIOD and lat < 1.5:
        pairs.append((i, j))
pairs = np.array(pairs)
_, lab = connected_components(coo_matrix((np.ones(len(pairs)), (pairs[:, 0], pairs[:, 1])),
                                         shape=(len(C), len(C))), directed=False)
chains = [np.flatnonzero(lab == k) for k in np.unique(lab)]

# 2. ring = chains that wrap all the way round; centre from a circle fit to them
def wraps(ids):
    v = C[ids] - C[ids].mean(0)
    a = np.sort(np.arctan2(v[:, 1], v[:, 0]))
    return len(ids) > 20 and np.diff(np.r_[a, a[0] + 2 * np.pi]).max() < np.radians(30)
ring = [ch for ch in chains if wraps(ch)]
rp = C[np.concatenate(ring)]
M = np.c_[2 * rp, np.ones(len(rp))]
cx, cy, _ = np.linalg.lstsq(M, (rp ** 2).sum(1), rcond=None)[0]
centre = np.array([cx, cy])
radii = sorted(np.hypot(*(C[ch] - centre).T).mean() for ch in ring)
outer = max(ring, key=lambda ch: np.hypot(*(C[ch] - centre).T).mean())
op = C[outer] - centre
order = np.argsort(np.arctan2(op[:, 1], op[:, 0]))
ring_edge = shapely.LinearRing(C[outer][order])
print(f"Étoile centre ({cx:.2f}, {cy:.2f}); {len(ring)} ring lines, mean radii " + ", ".join(f"{r:.1f}" for r in radii))

flag = []
print("\n-- yellow straightness (pieces >= 15 m) --")
devs = []
for i, m in enumerate(yellow):
    if m["len"] >= 15:
        devs.append(m["dev"])
        if m["dev"] > 0.10:
            flag.append(("y", i))
devs = np.array(devs)
print(f"pieces {len(devs)}: deviation from straight median {np.median(devs):.3f} m, "
      f"max {devs.max():.3f} m, >0.10 m: {(devs > 0.10).sum()}")

print("\n-- one-way streets carrying yellow --")
nodes, ways = load_osm(osm_path)
is_ow = lambda t: t.get("oneway") in ("yes", "-1", "1", "true") or t.get("junction") in ("roundabout", "circular")
oneway = [shapely.LineString([nodes[n] for n in w["nodes"]]) for w in ways if w.get("tags", {}).get("highway") and is_ow(w["tags"])]
twoway = [shapely.LineString([nodes[n] for n in w["nodes"]]) for w in ways if w.get("tags", {}).get("highway") and not is_ow(w["tags"])]
ot, tt = shapely.STRtree(oneway), shapely.STRtree(twoway)
bad_ow = 0
for i, m in enumerate(yellow):
    q = shapely.Point(m["c"])
    d1 = min((oneway[j].distance(q) for j in ot.query(q.buffer(10))), default=99)
    d2 = min((twoway[j].distance(q) for j in tt.query(q.buffer(10))), default=99)
    if d1 < 1.0 and d1 < d2:
        bad_ow += 1; flag.append(("y", i))
print(f"yellow pieces lying on a one-way street: {bad_ow}")

# 3. arms: non-ring lines whose inner end is within 25 m of the ring edge
ring_ids = set(np.concatenate(ring))
lines = []
for ch in chains:
    if ch[0] in ring_ids:
        continue
    pts = np.vstack([white[i]["pts"] for i in ch])
    lines.append({"kind": "w", "pts": pts, "n": len(ch), "ids": ch})
for i, m in enumerate(yellow):
    lines.append({"kind": "y", "pts": m["pts"], "n": None, "ids": [i]})
arm_lines = []
for L in lines:
    r = np.hypot(*(L["pts"] - centre).T)
    inner = L["pts"][np.argmin(r)]
    gap = ring_edge.distance(shapely.Point(inner))
    if r.min() > radii[-1] and gap < 25:
        c = L["pts"].mean(0)
        w, vec = np.linalg.eigh(np.cov((L["pts"] - c).T))
        L.update(gap=gap, c=c, ax=vec[:, 1], ang=np.degrees(np.arctan2(*(inner - centre)[::-1])))
        arm_lines.append(L)
arms = []
for L in sorted(arm_lines, key=lambda L: L["ang"]):
    if arms and (L["ang"] - arms[-1][-1]["ang"]) < 12:
        arms[-1].append(L)
    else:
        arms.append([L])
if len(arms) > 1 and arms[0][0]["ang"] + 360 - arms[-1][-1]["ang"] < 12:
    arms[0] = arms.pop() + arms[0]

print("\n-- avenues meeting the ring --")
LANE_W = 2.7
lane_edge = ring_edge.buffer(LANE_W).exterior  # outer edge of the ring's lane block
bad_arm, arm_gaps = 0, []
for arm in arms:
    ax = arm[0]["ax"] * np.sign(arm[0]["ax"] @ (arm[0]["c"] - centre))
    nrm = np.array([-ax[1], ax[0]])
    inner = [L["pts"][np.argmin((L["pts"] - centre) @ ax)] for L in arm]  # start of each line's first mark
    along = np.array([(p - centre) @ ax for p in inner])
    lat = np.array([(L["c"] - centre) @ nrm for L in arm])
    mid = (lat.max() + lat.min()) / 2
    par = max(np.degrees(np.arccos(min(1, abs(L["ax"] @ ax)))) for L in arm)
    row_mid = centre + ax * along.mean() + nrm * mid
    gap = lane_edge.distance(shapely.Point(row_mid))
    arm_gaps.append(gap)
    counts = [L["n"] for L in arm if L["kind"] == "w"]
    ylen = [round(float(np.ptp((L["pts"] - L["c"]) @ L["ax"])), 1) for L in arm if L["kind"] == "y"]
    issues = []
    if np.ptp(along) > 0.3: issues.append(f"rows not aligned ({np.ptp(along):.2f} m)")
    if len(set(counts)) > 1: issues.append("different dash counts")
    if par > 0.5: issues.append(f"lines not parallel ({par:.2f} deg)")
    radial = abs(mid) < 0.3
    bad_arm += bool(issues)
    print(f"arm @{np.mean([L['ang'] for L in arm]):6.1f} deg: {len(arm)} lines, dashes {counts}, yellow {ylen} m, "
          f"row gap to ring {gap:.2f} m, axis {'through centre' if radial else f'misses centre by {abs(mid):.2f} m'}"
          f"  -> {'; '.join(issues) or 'ok'}")
arm_gaps = np.array(arm_gaps)
print(f"arms with issues: {bad_arm} / {len(arms)}; ring gap across arms: min {arm_gaps.min():.2f} max {arm_gaps.max():.2f} m")

fig, ax = plt.subplots(figsize=(14, 12)); ax.set_facecolor("#333")
for lst, col, kind in ((white, "w", "w"), (yellow, "#f2be1a", "y")):
    ax.add_collection(PolyCollection([t for i, m in enumerate(lst) for t in m["tris"]],
                                     facecolors=col, edgecolors="none"))
for kind, i in flag:
    m = yellow[i]
    ax.add_collection(PolyCollection(list(m["tris"]), facecolors="r", edgecolors="r", linewidths=2))
ax.plot(*centre, "c+", ms=20)
ax.plot(*np.array(ring_edge.coords).T, "c-", lw=0.5)
for a in range(0, 360, 30):
    t = np.radians(a); ax.plot([cx, cx + 400 * np.cos(t)], [cy, cy + 400 * np.sin(t)], "c:", lw=0.3)
ax.set_aspect("equal"); ax.set_xlim(-200, 200); ax.set_ylim(-170, 170)
fig.savefig(out_png, dpi=110, bbox_inches="tight")
