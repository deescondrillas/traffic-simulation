#  Franco De Escondrillas ft. Claude Code · 2026-11-18
"""Widen the lanes of a built map so each street's lanes share its asphalt equally.

usage: equalize_lanes.py <obj> <vcolor obj> <road_graph.json> <out_dir>

build.py paints every lane LANE_W wide around the street axis, so the leftover asphalt ends up
in the two outer lanes. This keeps every axis (and so every line's direction) and only moves
the lane lines and lane paths sideways: line i of an n-lane street goes from
(i - n/2) * LANE_W to (i - n/2) * W / n off the axis, W being the asphalt width. The ring and
service roads (often drawn across open asphalt) are left alone.
"""
import collections
import json
import os
import sys

import numpy as np
import shapely
from shapely.geometry import LineString, Point

obj_path, vcolor_path, graph_path, out_dir = sys.argv[1:5]
LANE_W = 2.7
SNAP_TOL = 0.15      # how far a marking may sit from its expected line offset
RAY = 25.0           # m, longest half-width measured
OPENING_TOL = 0.4    # widths this far from the street median are side-street openings


def read_obj(path):
    """Vertex lines, faces per object and vertex index range per object."""
    lines = open(path).read().splitlines()
    verts, faces, span, name = [], collections.defaultdict(list), {}, None
    for k, ln in enumerate(lines):
        if ln.startswith("o "):
            name = ln.split()[1]
            span[name] = [len(verts), len(verts)]
        elif ln.startswith("v "):
            verts.append(k)
            span[name][1] = len(verts)
        elif ln.startswith("f "):
            faces[name].append([int(t.split("/")[0]) - 1 for t in ln.split()[1:]])
    return lines, verts, faces, span


lines, vline, faces, span = read_obj(obj_path)
V = np.array([list(map(float, lines[k].split()[1:4])) for k in vline])
P = np.c_[V[:, 0], -V[:, 2]]  # east/north

road_tris = P[np.array(faces["roads"])]
slab = shapely.union_all([shapely.Polygon(t) for t in road_tris if shapely.Polygon(t).area > 1e-6]).buffer(0)
edge = slab.boundary
shapely.prepare(edge)

# --- lanes per OSM way, forward-oriented, with their index across the street ---------------
graph = json.load(open(graph_path))
by_way = collections.defaultdict(list)
for lane in graph["lanes"]:
    by_way[lane["osm_way"]].append(lane)
ways = {}
for wid, ls in by_way.items():
    n, fw = len(ls), sum(l["direction"] == "forward" for l in ls)
    for l in ls:
        i = l["lane"] if l["direction"] == "forward" else n - 1 - l["lane"]
        pts = np.array(l["points"])[:, [0, 2]] * [1, -1]
        l["_i"], l["_path"] = i, LineString(pts if l["direction"] == "forward" else pts[::-1])
    key = (ls[0]["name"] or wid, ls[0]["highway"], n, fw)
    ways[wid] = {"lanes": ls, "n": n, "fw": fw, "ring": ls[0]["roundabout"], "key": key}


def old_off(i, n):
    """Offset of lane centre i (or line i, for integer i) left of the axis, as build.py paints it."""
    return (i + 0.5 - n / 2) * LANE_W


def axis_of(way):
    l = way["lanes"][0]
    return l["_path"].offset_curve(-old_off(l["_i"], way["n"]))


def widths_along(axis):
    out = []
    for t in np.arange(0.5, axis.length, 1.0):
        p = np.array(axis.interpolate(t).coords[0])
        q1, q2 = axis.interpolate(max(0, t - 0.5)), axis.interpolate(min(axis.length, t + 0.5))
        u = np.array(q2.coords[0]) - np.array(q1.coords[0])
        u /= np.linalg.norm(u) + 1e-12
        nrm = np.array([-u[1], u[0]])
        d = []
        for sgn in (1, -1):
            hit = LineString([p, p + sgn * nrm * RAY]).intersection(edge)
            d.append(Point(p).distance(hit) if not hit.is_empty else np.nan)
        out.append(d[0] + d[1])
    return out


# --- lane width per street: its asphalt width split equally -----------------------------
street_w = collections.defaultdict(list)
for way in ways.values():
    if not way["ring"] and way["n"] >= 2 and way["key"][1] != "service":
        street_w[way["key"]] += widths_along(axis_of(way))
lane_w = {}
for key, ws in street_w.items():
    ws = np.array(ws)
    ws = ws[~np.isnan(ws)]
    med = np.median(ws)
    W = np.median(ws[np.abs(ws - med) < OPENING_TOL]) if len(ws) else 0.0
    lane_w[key] = max(LANE_W, W / key[2])
    print(f"{str(key[0])[:28]:28s} {key[1]:10s} lanes {key[2]}  asphalt {W:5.2f} m  lane {LANE_W} -> {lane_w[key]:.2f} m")


def shift(i, way):
    """Sideways move of line/lane-centre i (lines: integer i, lane centres: i + 0.5)."""
    w, n = lane_w.get(way["key"], LANE_W), way["n"]
    return (i - n / 2) * (w - LANE_W)


# --- markings: each piece moves with its line -------------------------------------------
tree_lanes = [l for way in ways.values() for l in way["lanes"]]
tree = shapely.STRtree([l["_path"] for l in tree_lanes])
newP = P.copy()
moved, skipped = 0, []
for layer in ("markings_white", "markings_yellow"):
    f = np.array(faces[layer])
    parent = {}

    def find(a):
        while parent.setdefault(a, a) != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return a

    for a, b, c in f:
        parent[find(b)] = find(a); parent[find(c)] = find(a)
    pieces = collections.defaultdict(set)
    for tri in f:
        for v in tri:
            pieces[find(v)].add(v)
    for vs in pieces.values():
        vs = np.array(sorted(vs))
        c = Point(P[vs].mean(0))
        lane = tree_lanes[tree.nearest(c)]
        way = ways[lane["osm_way"]]
        if way["ring"] or way["key"] not in lane_w:
            continue
        path = lane["_path"]
        t = path.project(c)
        q = np.array(path.interpolate(t).coords[0])
        u = np.array(path.interpolate(min(path.length, t + 0.5)).coords[0]) - np.array(path.interpolate(max(0, t - 0.5)).coords[0])
        u /= np.linalg.norm(u) + 1e-12
        nrm = np.array([-u[1], u[0]])
        s = old_off(lane["_i"], way["n"]) + (np.array(c.coords[0]) - q) @ nrm
        i = round(s / LANE_W + way["n"] / 2)
        if not 1 <= i <= way["n"] - 1 or abs(s - (i - way["n"] / 2) * LANE_W) > SNAP_TOL:
            skipped.append((layer, way["key"][0], round(s, 2), np.round(c.coords[0], 1)))
            continue
        d = shift(i, way)
        for v in vs:  # each vertex along the normal of its own stretch, so bent lines stay offsets
            tv = path.project(Point(P[v]))
            a, b = (np.array(path.interpolate(x).coords[0]) for x in (max(0, tv - 0.5), min(path.length, tv + 0.5)))
            uv = (b - a) / (np.linalg.norm(b - a) + 1e-12)
            newP[v] = P[v] + np.array([-uv[1], uv[0]]) * d
        moved += 1
print(f"marking pieces moved {moved}, left alone {len(skipped)} (not on a widened street's line)")
for sk in skipped:
    print("  ", *sk)


def write_obj(src, dst):
    out = open(src).read().splitlines()
    vk = [k for k, ln in enumerate(out) if ln.startswith("v ")]
    assert len(vk) == len(V)
    for name in ("markings_white", "markings_yellow"):
        for v in range(*span[name]):
            parts = out[vk[v]].split()
            parts[1], parts[3] = f"{newP[v, 0]:.3f}", f"{-newP[v, 1]:.3f}"
            out[vk[v]] = " ".join(parts)
    open(dst, "w").write("\n".join(out) + "\n")


os.makedirs(out_dir, exist_ok=True)
write_obj(obj_path, os.path.join(out_dir, os.path.basename(obj_path)))
write_obj(vcolor_path, os.path.join(out_dir, os.path.basename(vcolor_path)))

# --- lane graph -----------------------------------------------------------------------------
for way in ways.values():
    for l in way["lanes"]:
        path, i = l.pop("_path"), l.pop("_i")
        if way["key"] not in lane_w:
            continue
        g = path.offset_curve(shift(i + 0.5, way), join_style="round", quad_segs=4)
        if g.geom_type == "MultiLineString":
            g = max(g.geoms, key=lambda x: x.length)
        pts = np.array(g.coords)
        if l["direction"] == "backward":
            pts = pts[::-1]
        y = l["points"][0][1]
        l["points"] = [[round(x, 2), y, round(-z, 2)] for x, z in pts]
        l["width_m"] = round(lane_w[way["key"]], 2)
json.dump(graph, open(os.path.join(out_dir, os.path.basename(graph_path)), "w"))
