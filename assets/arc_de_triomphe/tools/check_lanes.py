#  Franco De Escondrillas ft. Claude Code · 2026-11-18
"""Check road_graph.json lane paths sit midway between painted stripes (ideal: width_m / 2 from stripe centre).

usage: check_lanes.py <obj> <road_graph.json>
"""
import json
import sys

import numpy as np
import shapely

obj, graph = sys.argv[1:3]
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
ds = []  # (distance to stripe centre, ideal)
for lane in json.load(open(graph))["lanes"]:
    half = lane["width_m"] / 2
    line = shapely.LineString(np.array(lane["points"])[:, [0, 2]] * [1, -1])
    for t in np.arange(0, line.length, 2.0):
        d = line.interpolate(t).distance(paint)
        if d < half + 1.0:
            ds.append((d + 0.075, half))  # to stripe centreline
ds = np.array(ds)
err = ds[:, 0] - ds[:, 1]
print(f"lane path to nearest stripe centre minus ideal (width_m / 2): median {np.median(err):+.3f}  "
      f"p10 {np.percentile(err, 10):+.3f}  p90 {np.percentile(err, 90):+.3f}; within 0.1 m: {100 * np.mean(abs(err) < 0.1):.1f}%")
