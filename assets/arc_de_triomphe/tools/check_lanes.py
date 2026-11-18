#  Franco De Escondrillas ft. Claude Code · 2026-11-09
"""Check road_graph.json lane paths sit midway between painted stripes (ideal: lane_w / 2 from stripe centre).

usage: check_lanes.py <obj> <road_graph.json> [lane_w=2.7]
"""
import json
import sys

import numpy as np
import shapely

obj, graph = sys.argv[1:3]
half = (float(sys.argv[3]) if len(sys.argv) > 3 else 2.7) / 2
V, G, g = [], {}, None
for ln in open(obj):
    if ln.startswith("v "):
        V.append(list(map(float, ln.split()[1:4])))
    elif ln.startswith("o "):
        g = ln.split()[1]; G[g] = []
    elif ln.startswith("f ") and g.startswith("markings"):
        G[g].append([int(t.split("/")[0]) - 1 for t in ln.split()[1:]])
V = np.array(V); P = np.c_[V[:, 0], -V[:, 2]]
paint = shapely.union_all([shapely.Polygon(t) for k, f in G.items() if f for t in P[np.array(f)]])
ds = []
for lane in json.load(open(graph))["lanes"]:
    line = shapely.LineString(np.array(lane["points"])[:, [0, 2]] * [1, -1])
    for t in np.arange(0, line.length, 2.0):
        d = line.interpolate(t).distance(paint)
        if d < half + 1.0:
            ds.append(d + 0.075)  # to stripe centreline
ds = np.array(ds)
print(f"lane path to nearest stripe centre: median {np.median(ds):.3f}  p10 {np.percentile(ds, 10):.3f}  "
      f"p90 {np.percentile(ds, 90):.3f}  (ideal {half:.3f}); within 0.1 m: {100 * np.mean(abs(ds - half) < 0.1):.1f}%")
