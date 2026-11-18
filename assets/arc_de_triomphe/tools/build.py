#  Franco De Escondrillas ft. Claude Code · 2026-11-09
"""Build the simulation map: OBJ/MTL (+ vertex-colour OBJ) and a lane graph from 3MF + OSM.

usage: build.py <3mf> <osm.json> <align.json> <out_dir>

Output frame: metres, Y-up, origin at the Arc; +X = east, -Z = north.
"""
import collections
import json
import os
import sys

import numpy as np
import shapely
from shapely.geometry import LineString, Polygon
from shapely.ops import unary_union

from common import load_osm, raster
from parse3mf import load

src, osm_path, align_path, out_dir = sys.argv[1:5]
os.makedirs(out_dir, exist_ok=True)
parts = load(src)
nodes, ways = load_osm(osm_path)
a = json.load(open(align_path))

# --- mesh: print mm -> metres ------------------------------------------------
GROUND_MM = 1.0
ROAD_TOP, PARK_TOP, PLATE_DEPTH = 0.15, 0.10, 0.5
MARK_Z = ROAD_TOP + 0.02
_c, _s = np.cos(a["theta"]), np.sin(a["theta"])


def to_xy(p):
    q = p[:, :2] - a["centre_mm"]
    return a["scale"] * np.c_[_c * q[:, 0] - _s * q[:, 1], _s * q[:, 0] + _c * q[:, 1]] + [a["tx"], a["ty"]]


def flatten(v, top_m, z0=GROUND_MM):
    """Squash a thin slab sitting on the ground plate to `top_m` metres thick."""
    z = v[:, 2] - z0
    return z / z.max() * top_m


layers = {}  # name -> (xyz in east/north/up, faces)
v, f = parts["3"]
layers["buildings"] = (np.c_[to_xy(v), (v[:, 2] - GROUND_MM) * a["scale"]], f)
v, f = parts["4"]
layers["roads"] = (np.c_[to_xy(v), flatten(v, ROAD_TOP)], f)
pv, pf = [], []
for k in ("1", "2"):
    v, f = parts[k]
    pf.append(f + sum(len(x) for x in pv)); pv.append(np.c_[to_xy(v), flatten(v, PARK_TOP)])
layers["parks"] = (np.vstack(pv), np.vstack(pf))
v, f = parts["6"]
layers["ground"] = (np.c_[to_xy(v), v[:, 2] / GROUND_MM * PLATE_DEPTH - PLATE_DEPTH], f)

# --- road slab footprint -------------------------------------------------------
rv, rf = layers["roads"]
slab = unary_union([Polygon(t) for t in rv[rf][:, :, :2] if Polygon(t).area > 1e-6]).buffer(0)
gv, _ = layers["ground"]
EXT = (gv[:, 0].min(), gv[:, 0].max(), gv[:, 1].min(), gv[:, 1].max())
RES = 0.2
slab_mask = raster(rv[rf][:, :, :2], EXT, RES)


def inside(p):
    ix = ((p[..., 0] - EXT[0]) / RES).astype(int)
    iy = ((p[..., 1] - EXT[2]) / RES).astype(int)
    ok = (ix >= 0) & (iy >= 0) & (ix < slab_mask.shape[1]) & (iy < slab_mask.shape[0])
    out = np.zeros(ix.shape, bool)
    out[ok] = slab_mask[iy[ok], ix[ok]]
    return out


# --- OSM car roads ---------------------------------------------------------------
CAR = {"motorway", "trunk", "primary", "secondary", "tertiary", "unclassified", "residential",
       "living_street", "service", "primary_link", "secondary_link", "tertiary_link"}
MAJOR = {"primary", "secondary", "tertiary", "trunk", "motorway"}
STEP = 2.0
roads = []
for w in ways:
    t = w.get("tags", {})
    if t.get("highway") not in CAR or t.get("area") == "yes":
        continue
    ids = w["nodes"]
    if t.get("oneway") == "-1":
        ids = ids[::-1]
    line = LineString([nodes[n] for n in ids])
    if line.length < 1 or not line.intersects(slab):
        continue
    roads.append({"way": w, "tags": t, "ids": ids, "line": line})

tree = shapely.STRtree([r["line"] for r in roads])
degree = collections.Counter()
for r in (r for r in roads if r["tags"]["highway"] != "service"):
    for i, n in enumerate(r["ids"]):
        degree[n] += 1 if i in (0, len(r["ids"]) - 1) else 2


def lane_split(t):
    oneway = t.get("oneway") in ("yes", "-1", "true", "1") or t.get("junction") in ("roundabout", "circular")
    n = int(t["lanes"]) if t.get("lanes", "").isdigit() else (1 if oneway else 2)
    if oneway:
        return n, 0
    fw, bw = t.get("lanes:forward", ""), t.get("lanes:backward", "")
    if fw.isdigit() and bw.isdigit():
        return int(fw), int(bw)
    return max(1, n - n // 2), max(1, n // 2)


def rolling_median(x, k=7):
    pad = np.pad(x, k // 2, mode="edge")
    return np.array([np.nanmedian(pad[i:i + k]) for i in range(len(x))])


JUNCTION_R = 9.0
SNAP = 4.0
junction_pts = np.array([nodes[n] for n, k in degree.items() if k >= 3])
offsets = np.arange(-30, 30 + RES / 2, RES / 2)


def slab_interval(p, nor):
    """Slab interval [lo, hi] along the normal through p, the one containing or nearest to p."""
    ins = inside(p + nor * offsets[:, None])
    if not ins.any():
        return None
    edges = np.flatnonzero(np.diff(np.r_[0, ins.astype(int), 0]))
    runs = [(offsets[s], offsets[e - 1]) for s, e in zip(edges[::2], edges[1::2])]
    lo, hi = min(runs, key=lambda r: 0 if r[0] <= 0 <= r[1] else min(abs(r[0]), abs(r[1])))
    if lo > SNAP or hi < -SNAP:
        return None
    return lo, hi


def parallel_limit(p, t, nor, sgn, reach, others):
    """Halve the gap to a parallel carriageway hit by the ray, ignoring crossing roads."""
    ray = LineString([p, p + sgn * nor * reach])
    for ol in others:
        hit = ray.intersection(ol)
        if hit.is_empty:
            continue
        hp = shapely.ops.nearest_points(shapely.Point(p), hit)[1]  # hit may be a point, multipoint or overlap
        s = ol.project(hp)
        q1, q2 = np.array(ol.interpolate(s - 1).coords[0]), np.array(ol.interpolate(s + 1).coords[0])
        ot = (q2 - q1) / (np.linalg.norm(q2 - q1) + 1e-12)
        if abs(ot @ t) > 0.85:
            reach = min(reach, hp.distance(shapely.Point(p)) / 2)
    return reach


def measure(r):
    """Sample the centreline; for each sample find left/right slab extents (L, R)."""
    line = r["line"]
    n = max(2, int(line.length / STEP) + 1)
    d = np.linspace(0, line.length, n)
    p = np.array([line.interpolate(x).coords[0] for x in d])
    tan = np.gradient(p, axis=0)
    tan /= np.linalg.norm(tan, axis=1, keepdims=True) + 1e-12
    nor = np.c_[-tan[:, 1], tan[:, 0]]  # left normal
    inbox = (p[:, 0] > EXT[0]) & (p[:, 0] < EXT[1]) & (p[:, 1] > EXT[2]) & (p[:, 1] < EXT[3])
    if inbox.sum() < 2:
        return None
    near_j = (np.min(np.linalg.norm(p[:, None] - junction_pts[None], axis=2), axis=1) < JUNCTION_R
              if len(junction_pts) else np.zeros(n, bool))
    others = [roads[j]["line"] for j in tree.query(line.buffer(30)) if roads[j] is not r]
    ext = np.full((n, 2), np.nan)
    for i in np.flatnonzero(inbox & ~near_j):
        iv = slab_interval(p[i], nor[i])
        if iv is None:
            continue
        lo, hi = iv
        L = parallel_limit(p[i], tan[i], nor[i], 1, hi, others) if hi > 0 else hi
        R = parallel_limit(p[i], tan[i], nor[i], -1, -lo, others) if lo < 0 else -lo
        ext[i] = L, R
    measured = ~np.isnan(ext[:, 0])
    if measured.sum() < 2 or measured.sum() < 0.3 * (inbox & ~near_j).sum():
        return None
    ext[:, 0], ext[:, 1] = rolling_median(ext[:, 0]), rolling_median(ext[:, 1])
    good = ~np.isnan(ext[:, 0])
    # bridge junctions (and short gaps) by interpolation so lanes stay continuous
    for k in (0, 1):
        ext[:, k] = np.interp(d, d[good], ext[good, k])
    ok = inbox & (good | near_j)
    return d, p, nor, ext, ok


LANE_W = 2.7      # every lane, every street
LINE_W = 0.15
DASH_ON, DASH_OFF = 3.0, 5.0
MARGIN = 0.3      # min gap between outer lane and slab edge
CENTRE_JITTER = 0.5
PRIORITY = {"primary": 0, "trunk": 0, "motorway": 0, "secondary": 1, "tertiary": 2,
            "unclassified": 3, "residential": 3, "living_street": 4, "service": 5}


def runs_of(mask, max_gap=5):
    """Index runs where mask is True, bridging gaps of up to max_gap samples."""
    idx = np.flatnonzero(mask)
    if len(idx) < 2:
        return []
    out, start = [], idx[0]
    for a, b in zip(idx[:-1], idx[1:]):
        if b - a > max_gap + 1:
            out.append((start, a)); start = b
    out.append((start, idx[-1]))
    return [(a, b) for a, b in out if b > a]


def smooth(x, k):
    if k < 2:
        return x
    pad = np.pad(x, k // 2, mode="edge")
    return np.convolve(pad, np.ones(k) / k, mode="valid")[:len(x)]


def lane_counts(t, width):
    fw, bw = lane_split(t)
    fit = max(1, int((width - 2 * MARGIN) // LANE_W))
    if bw == 0:
        return min(fw, fit), 0
    per_side = max(1, fit // 2)
    fw, bw = min(fw, per_side), min(bw, per_side)
    if fw + bw < fit and (fw < lane_split(t)[0] or bw < lane_split(t)[1]):
        if lane_split(t)[0] > fw: fw += 1
        elif lane_split(t)[1] > bw: bw += 1
    return fw, bw


def offset(line, off):
    g = line.offset_curve(off, join_style="round", quad_segs=4) if abs(off) > 1e-6 else line
    if g.geom_type == "MultiLineString":
        g = max(g.geoms, key=lambda x: x.length)
    return g


def chain(lines, tol=3.0):
    """Join same-street pieces end-to-start (gap < tol, similar heading); close loops."""
    pcs = [np.array(l.coords) for l in lines]
    joined = True
    while joined:
        joined = False
        for i in range(len(pcs)):
            for j in range(len(pcs)):
                if i == j:
                    continue
                a, b = pcs[i], pcs[j]
                ha, hb = a[-1] - a[-2], b[1] - b[0]
                cosang = ha @ hb / (np.linalg.norm(ha) * np.linalg.norm(hb) + 1e-12)
                if np.linalg.norm(a[-1] - b[0]) < tol and cosang > 0.8:
                    pcs[i] = np.vstack([a, b[1:]]) if np.allclose(a[-1], b[0]) else np.vstack([a, b])
                    del pcs[j]
                    joined = True
                    break
            if joined:
                break
    out = []
    for c in pcs:
        closed = len(c) > 3 and np.linalg.norm(c[-1] - c[0]) < tol
        out.append(fair(LineString(c), closed))
    return out


def fair(line, closed, step=1.0, window=15):
    """Resample at `step` m and moving-average over `window` samples: removes kinks, keeps straights straight."""
    n = max(2, int(line.length / step) + 1)
    pts = np.array([line.interpolate(t).coords[0] for t in np.linspace(0, line.length, n)])
    if closed:
        pts = pts[:-1]
        k = window // 2
        ext = np.vstack([pts[-k:], pts, pts[:k]])
        sm = np.c_[np.convolve(ext[:, 0], np.ones(window) / window, "valid"),
                   np.convolve(ext[:, 1], np.ones(window) / window, "valid")]
        sm = np.vstack([sm, sm[:1]])
    elif n > window:
        sm = np.c_[smooth(pts[:, 0], window), smooth(pts[:, 1], window)]
        sm[0], sm[-1] = pts[0], pts[-1]
    else:
        sm = pts
    return LineString(sm).simplify(0.01)


def on_painted_centre(raw, centres):
    """This way's stretch of the faired street centreline, so lane paths sit exactly between the paint."""
    a, b = shapely.Point(raw.coords[0]), shapely.Point(raw.coords[-1])
    c = min(centres, key=lambda x: x.distance(raw.interpolate(0.5, normalized=True)))
    if c.distance(raw.interpolate(0.5, normalized=True)) > 3.0:
        return None
    s0, s1 = c.project(a), c.project(b)
    if s1 > s0:
        return shapely.ops.substring(c, s0, s1)
    if c.is_closed:  # stretch wraps past the loop seam
        p1 = np.array(shapely.ops.substring(c, s0, c.length).coords)
        p2 = np.array(shapely.ops.substring(c, 0, s1).coords)
        return LineString(np.vstack([p1, p2[1:]]))
    return None


white_dashes, yellow_lines, graph = [], [], []
plans, node_w = [], collections.defaultdict(list)
for k, r in enumerate(roads):
    m = measure(r)
    if m is None:
        continue
    d, p, nor, ext, ok = m
    L, R = ext[:, 0], ext[:, 1]
    width = float(np.nanmedian((L + R)[ok]))
    co = (L - R) / 2
    co_const = np.nanmedian(co[ok])
    co = np.full_like(co, co_const) if np.nanstd(co[ok]) < CENTRE_JITTER else smooth(co, 15)
    centres = []
    for a, b in runs_of(ok):
        pts = p[a:b + 1] + nor[a:b + 1] * co[a:b + 1, None]
        c = LineString(pts).simplify(0.05)
        if c.length > DASH_ON:
            centres.append(c)
    fw, bw = lane_counts(r["tags"], width)
    rb = r["tags"].get("junction") in ("roundabout", "circular")
    plans.append({"r": r, "k": k, "centres": centres, "fw": fw, "bw": bw, "width": width, "rb": rb})
    for nid in r["ids"]:
        if degree[nid] >= 3:
            node_w[nid].append((k, width, rb))


def zones_for(plan):
    """Breaks where a non-ring road crosses, sized by its width. The ring's own clearance handles ring mouths."""
    if plan["rb"]:
        return []
    out = []
    for nid in plan["r"]["ids"]:
        others = [w for k, w, rb in node_w.get(nid, []) if k != plan["k"] and not rb]
        if others:
            out.append(shapely.Point(nodes[nid]).buffer(max(others) / 2 + 1.0))
    return out


groups = collections.defaultdict(list)
for pl in plans:
    t = pl["r"]["tags"]
    groups[(t.get("name", pl["k"]), t["highway"], pl["fw"], pl["bw"], pl["rb"])].append(pl)
street_centres = {key: [g for g in chain([c for pl in m for c in pl["centres"]]) if g.length > DASH_ON]
                  for key, m in groups.items()}

# Étoile centre: circle fitted to the ring's painted centreline
_rp = np.vstack([np.array(c.coords) for key, cs in street_centres.items() if key[4] for c in cs])
_cx, _cy, _ = np.linalg.lstsq(np.c_[2 * _rp, np.ones(len(_rp))], (_rp ** 2).sum(1), rcond=None)[0]
ETOILE = np.array([_cx, _cy])
RING_R = np.hypot(*(_rp - ETOILE).T).max()
STRAIGHT_TOL = 1.5  # wobble below this is flattened; real bends become corners
AVENUE_GAP = 3.0    # every avenue's first dash row starts this far from the ring's lane block


def straighten(c, margin):
    """Straight runs between real bends. The run touching the Étoile becomes an exact ray through
    its centre when that ray keeps the whole lane block on this street's asphalt."""
    pts = np.array(c.simplify(STRAIGHT_TOL).coords)
    for end, nxt in ((0, 1), (-1, -2)):
        a, b = pts[end], pts[nxt]
        if np.linalg.norm(a - ETOILE) > RING_R + 25:
            continue
        q = np.array([a, b]) - ETOILE
        u = np.linalg.eigh(q.T @ q)[1][:, 1]
        ray = LineString([ETOILE + u * (q[0] @ u), ETOILE + u * (q[1] @ u)])
        seg = LineString([a, b])
        dev = max(ray.distance(shapely.Point(x)) for x in c.coords
                  if seg.distance(shapely.Point(x)) < STRAIGHT_TOL + 0.5)
        if dev <= margin - 0.2:
            pts[end], pts[nxt] = ray.coords[0], ray.coords[1]
    return LineString(pts)


def straight_fit(c, through=None):
    """One straight line over the whole street (optionally forced through `through`)."""
    pts = np.array([c.interpolate(t).coords[0] for t in np.linspace(0, c.length, max(2, int(c.length) + 1))])
    o = pts.mean(0) if through is None else through
    q = pts - o
    u = np.linalg.eigh(q.T @ q)[1][:, 1]
    if u @ (pts[-1] - pts[0]) < 0:
        u = -u
    return LineString([o + u * (q[0] @ u), o + u * (q[-1] @ u)])


SLAB_EDGE = slab.boundary
shapely.prepare(SLAB_EDGE)
RADIAL_MAX_DEG = 0.15  # use the ray through the Étoile only when the asphalt itself is that radial


def fit_edges(c, iters=3):
    """(origin, direction) of the straight axis midway between the asphalt edges along `c`."""
    line = straight_fit(c)
    o = v = None
    for _ in range(iters):
        a, b = np.array(line.coords)
        u = (b - a) / np.linalg.norm(b - a); n = np.array([-u[1], u[0]])
        mids, ws = [], []
        for t in np.arange(0.5, line.length, 1.0):
            p = a + u * t
            d = []
            for sgn in (1, -1):
                hit = LineString([p, p + sgn * n * 20]).intersection(SLAB_EDGE)
                d.append(shapely.Point(p).distance(hit) if not hit.is_empty else np.nan)
            mids.append(p + n * (d[0] - d[1]) / 2); ws.append(d[0] + d[1])
        mids, ws = np.array(mids), np.array(ws)
        ok = ~np.isnan(ws)
        ok &= np.abs(ws - np.nanmedian(ws)) < 0.4  # side-street openings
        if ok.sum() < 5:
            return None
        m = mids[ok]
        for _ in range(3):  # robust: drop outliers and refit
            o = m.mean(0)
            v = np.linalg.eigh(np.cov((m - o).T))[1][:, 1]
            res = np.abs((m - o) @ np.array([-v[1], v[0]]))
            if res.max() < 0.15:
                break
            m = m[res < max(0.15, np.percentile(res, 80))]
        if v @ u < 0:
            v = -v
        line = LineString([o + v * ((a - o) @ v), o + v * ((b - o) @ v)])
    return o, v


def angle_between(v1, v2):
    return np.degrees(np.arccos(min(1.0, abs(v1 @ v2))))


def edge_fit(c, bend_tol=0.6, min_piece=15.0, merge_deg=0.3):
    """Axis parallel to the asphalt edges: straight pieces between real bends, each fitted to its own
    edges, joined at corners. Returns (polyline, number of pieces)."""
    cut = sorted({c.project(shapely.Point(q)) for q in c.simplify(bend_tol).coords} | {0.0, c.length})
    spans = [[a, b] for a, b in zip(cut, cut[1:]) if b - a > 1e-6]
    while len(spans) > 1 and min(b - a for a, b in spans) < min_piece:  # fold short pieces into a neighbour
        k = min(range(len(spans)), key=lambda i: spans[i][1] - spans[i][0])
        j = k - 1 if k > 0 else k + 1
        lo, hi = min(k, j), max(k, j)
        spans[lo:hi + 1] = [[spans[lo][0], spans[hi][1]]]
    fits = [fit_edges(shapely.ops.substring(c, a, b)) for a, b in spans]
    if any(f is None for f in fits):
        return None, 0
    merged = True
    while merged and len(spans) > 1:  # neighbours that are really one straight run get one fit
        merged = False
        for i in range(len(spans) - 1):
            if angle_between(fits[i][1], fits[i + 1][1]) < merge_deg:
                spans[i:i + 2] = [[spans[i][0], spans[i + 1][1]]]
                f = fit_edges(shapely.ops.substring(c, *spans[i]))
                if f is None:
                    return None, 0
                fits[i:i + 2] = [f]
                merged = True
                break
    p0, p1 = np.array(c.coords[0]), np.array(c.coords[-1])
    pts = [fits[0][0] + fits[0][1] * ((p0 - fits[0][0]) @ fits[0][1])]
    for (o1, v1), (o2, v2) in zip(fits, fits[1:]):  # corner = intersection of consecutive axes
        M = np.c_[v1, -v2]
        t = np.linalg.solve(M, o2 - o1)
        pts.append(o1 + v1 * t[0])
    pts.append(fits[-1][0] + fits[-1][1] * ((p1 - fits[-1][0]) @ fits[-1][1]))
    return LineString(pts), len(fits)


def candidates(c, margin):
    """Preferred first: a ray through the Étoile centre (only where the asphalt is radial),
    the straight axis between the asphalt edges, then straight runs with corners."""
    out = []
    axis, pieces = edge_fit(c)
    near = min(np.linalg.norm(np.array(c.coords[0]) - ETOILE), np.linalg.norm(np.array(c.coords[-1]) - ETOILE))
    if axis is not None:
        if near < RING_R + 25 and pieces == 1:
            ray = straight_fit(c, ETOILE)
            ua = np.diff(np.array(axis.coords), axis=0)[0]; ur = np.diff(np.array(ray.coords), axis=0)[0]
            ang = np.degrees(np.arccos(min(1, abs(ua @ ur) / np.linalg.norm(ua) / np.linalg.norm(ur))))
            mid = np.array(axis.interpolate(0.5, normalized=True).coords[0])
            if ang <= RADIAL_MAX_DEG and ray.distance(shapely.Point(mid)) < 0.3:
                out.append(ray)
        out.append(axis)
    out.append(straighten(c, margin))
    return out


street_margin = {key: (np.median([pl["width"] for pl in m]) - (key[2] + key[3]) * LANE_W) / 2
                 for key, m in groups.items()}
RING_BLOCK = shapely.Polygon()

PERIOD = DASH_ON + DASH_OFF
SCAN = 0.1          # search step for the first dash row after a break
RING_CLEAR = 1.0    # gap between the ring's lane block and the first row on an avenue


def ring_start(c, back):
    """Arc position (from the Étoile end) where the axis is AVENUE_GAP clear of the ring's lane block."""
    if RING_BLOCK.is_empty:
        return None
    end = np.array(c.coords[-1] if back else c.coords[0])
    if np.linalg.norm(end - ETOILE) > RING_R + 25:
        return None
    for d in np.arange(0, min(60.0, c.length), 0.02):
        if RING_BLOCK.distance(c.interpolate(c.length - d if back else d)) >= AVENUE_GAP:
            return d
    return None


def place_rows(c, offs, allowed):
    """Dash rows across all lane lines at once, scanning from the end nearest the Étoile.
    A row is kept only if every line's dash fits, so all lanes get the same dashes.
    Avenues meeting the ring start their first row exactly AVENUE_GAP from it."""
    lns = [offset(c, o) for o in offs]
    def row(s):
        out = []
        for ln in lns:
            t = ln.project(c.interpolate(s))
            if t + DASH_ON > ln.length + 1e-6:
                return None
            seg = shapely.ops.substring(ln, t, t + DASH_ON)
            if not shapely.contains_properly(allowed, seg.buffer(LINE_W / 2, cap_style="flat")):
                return None
            out.append(seg)
        return out
    back = np.linalg.norm(np.array(c.coords[-1]) - ETOILE) < np.linalg.norm(np.array(c.coords[0]) - ETOILE)
    d0 = ring_start(c, back) or 0.0
    rows, s = {}, (c.length - DASH_ON - d0 if back else d0)
    while 0 <= s <= c.length - DASH_ON + 1e-9:
        r = row(s)
        if r:
            rows[s] = r
            s += -PERIOD if back else PERIOD
        else:
            s += -SCAN if back else SCAN
    keys = sorted(rows)
    runs, cur = [], keys[:1]
    for a, b in zip(keys, keys[1:]):
        if abs(b - a - PERIOD) < 1e-6:
            cur.append(b)
        else:
            runs.append(cur); cur = [b]
    if cur:
        runs.append(cur)
    return lns, [[(s, rows[s]) for s in run] for run in runs if len(run) > 1]


drive = slab.buffer(-0.05)
placed = shapely.Polygon()
order = sorted(groups.items(), key=lambda kv: (not kv[0][4], PRIORITY.get(kv[0][1], 9),
                                                -sum(pl["r"]["line"].length for pl in kv[1])))
for key, members in order:
    _, _, fw, bw, rb = key
    n = fw + bw
    total = n * LANE_W
    centres = street_centres[key]
    if not centres:
        continue
    allowed = drive.difference(unary_union([z for pl in members for z in zones_for(pl)])).difference(
        placed.buffer(RING_CLEAR))
    shapely.prepare(allowed)
    offs = [-total / 2 + i * LANE_W for i in range(1, n)]
    if not rb and offs:
        chosen = []
        for raw in centres:
            tried = [(cand, place_rows(cand, offs, allowed)) for cand in candidates(raw, street_margin[key])]
            rows = [sum(len(r) for r in res[1]) for _, res in tried]
            need = max(rows) - max(1, int(0.05 * max(rows)))
            chosen.append(next(cand for (cand, _), k in zip(tried, rows) if k >= need))
        centres = street_centres[key] = chosen
    for c in centres:
        offs = [-total / 2 + i * LANE_W for i in range(1, n)]
        if not offs:
            continue
        if c.is_closed:  # ring: whole number of dashes per loop, exact period on each line
            for i, off in enumerate(offs, start=1):
                ln = offset(c, off)
                per = ln.length / round(ln.length / PERIOD)
                for t in np.arange(round(ln.length / per)) * per:
                    seg = shapely.ops.substring(ln, t, t + DASH_ON)
                    if shapely.contains(allowed, seg.buffer(LINE_W / 2, cap_style="flat")):
                        white_dashes.append(seg)
            continue
        lns, runs = place_rows(c, offs, allowed)
        for run in runs:
            for i, ln in enumerate(lns, start=1):
                if i == fw and bw:  # solid centre line spanning exactly the run's rows
                    s0, s1 = run[0][1][i - 1], run[-1][1][i - 1]
                    a, b = ln.project(shapely.Point(s0.coords[0])), ln.project(shapely.Point(s1.coords[-1]))
                    yellow_lines.append(shapely.ops.substring(ln, min(a, b), max(a, b)))
                else:
                    white_dashes += [segs[i - 1] for _, segs in run]
    placed = placed.union(unary_union([c.buffer(total / 2, cap_style="flat") for c in centres]))
    if rb:
        RING_BLOCK = RING_BLOCK.union(unary_union([c.buffer(total / 2) for c in centres]))
    for pl in members:
        r = pl["r"]
        for raw in pl["centres"]:
            c = on_painted_centre(raw, centres)
            if c is None:
                continue
            for i in range(n):
                pts = np.array(offset(c, -total / 2 + (i + 0.5) * LANE_W).coords)
                graph.append({
                    "osm_way": r["way"]["id"], "name": r["tags"].get("name", ""), "highway": r["tags"]["highway"],
                    "roundabout": rb, "lane": i if i < fw else n - 1 - i,
                    "direction": "forward" if i < fw else "backward",
                    "from_node": r["ids"][0] if i < fw else r["ids"][-1],
                    "to_node": r["ids"][-1] if i < fw else r["ids"][0],
                    "width_m": LANE_W, "points": pts if i < fw else pts[::-1],
                })


def ribbons(lines):
    return shapely.multipolygons([ln.buffer(LINE_W / 2, cap_style="flat") for ln in lines])


def triangulate(geom, z):
    verts, faces = [], []
    tris = shapely.constrained_delaunay_triangles(geom)
    for t in shapely.get_parts(tris):
        c = np.array(t.exterior.coords)[:3]
        if abs(shapely.area(t)) < 1e-6:
            continue
        e1, e2 = c[1] - c[0], c[2] - c[0]
        if e1[0] * e2[1] - e1[1] * e2[0] < 0:
            c = c[::-1]
        faces.append(np.arange(3) + len(verts) * 3)
        verts.append(c)
    if not verts:
        return np.zeros((0, 3)), np.zeros((0, 3), int)
    v = np.vstack(verts)
    return np.c_[v, np.full(len(v), z)], np.array(faces)


layers["markings_white"] = triangulate(ribbons(white_dashes), MARK_Z)
layers["markings_yellow"] = triangulate(ribbons(yellow_lines), MARK_Z + 0.005)

# --- export --------------------------------------------------------------------
COLORS = {"ground": (0.06, 0.06, 0.07), "roads": (0.33, 0.33, 0.35), "parks": (0.42, 0.50, 0.40),
          "buildings": (0.93, 0.93, 0.92), "markings_white": (0.95, 0.95, 0.95),
          "markings_yellow": (0.95, 0.75, 0.10)}
ORDER = ["ground", "roads", "parks", "buildings", "markings_white", "markings_yellow"]


def gl(v):  # east/north/up -> OpenGL Y-up
    return np.c_[v[:, 0], v[:, 2], -v[:, 1]]


def weld(v, f):
    key = np.round(v, 4)
    uniq, inv = np.unique(key, axis=0, return_inverse=True)
    f = inv.reshape(-1)[f]
    f = f[(f[:, 0] != f[:, 1]) & (f[:, 1] != f[:, 2]) & (f[:, 0] != f[:, 2])]
    return uniq, f


def write_obj(path, vcolor):
    base = os.path.splitext(os.path.basename(path))[0]
    vo = no = 0
    stats = {}
    with open(path, "w") as fh:
        fh.write("# Arc de Triomphe / Place Charles de Gaulle simulation map\n"
                 "# units: metres, Y-up, origin at the Arc, +X east, -Z north\n")
        if not vcolor:
            fh.write(f"mtllib {base}.mtl\n")
        for name in ORDER:
            v, f = weld(*layers[name])
            v = gl(v)
            n = np.cross(v[f[:, 1]] - v[f[:, 0]], v[f[:, 2]] - v[f[:, 0]])
            n /= np.linalg.norm(n, axis=1, keepdims=True) + 1e-12
            fh.write(f"o {name}\n")
            if vcolor:
                r, g, b = COLORS[name]
                fh.write("".join(f"v {x:.3f} {y:.3f} {z:.3f} {r} {g} {b}\n" for x, y, z in v))
            else:
                fh.write("".join(f"v {x:.3f} {y:.3f} {z:.3f}\n" for x, y, z in v))
                fh.write(f"usemtl {name}\n")
            fh.write("".join(f"vn {x:.4f} {y:.4f} {z:.4f}\n" for x, y, z in n))
            fh.write("".join(f"f {a + vo}//{k + no} {b + vo}//{k + no} {c + vo}//{k + no}\n"
                             for k, (a, b, c) in enumerate(f + 1, start=1)))
            vo += len(v); no += len(f)
            stats[name] = len(f)
    return stats


stats = write_obj(os.path.join(out_dir, "arc_de_triomphe.obj"), False)
write_obj(os.path.join(out_dir, "arc_de_triomphe_vcolor.obj"), True)
with open(os.path.join(out_dir, "arc_de_triomphe.mtl"), "w") as fh:
    for name in ORDER:
        r, g, b = COLORS[name]
        fh.write(f"newmtl {name}\nKa 0 0 0\nKd {r} {g} {b}\nKs 0 0 0\nd 1\nillum 1\n\n")

for lane in graph:
    c = lane["points"]
    lane["points"] = [[round(x, 2), ROAD_TOP, round(-y, 2)] for x, y in c]
json.dump({"frame": "metres, Y-up, origin at Arc de Triomphe, +X east, -Z north",
           "drive_side": "right", "lanes": graph},
          open(os.path.join(out_dir, "road_graph.json"), "w"))
json.dump({"faces": stats, "lanes": len(graph), "white_dashes": len(white_dashes), "yellow_lines": len(yellow_lines)},
          sys.stdout, indent=1)
