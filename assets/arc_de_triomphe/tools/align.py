#  Franco De Escondrillas ft. Claude Code · 2026-11-09
"""Fit mesh(mm) -> OSM local metres similarity transform by building-footprint overlap.

usage: align.py <3mf> <osm.json> <out.json>
"""
import json
import sys

import numpy as np
from scipy.optimize import minimize

from common import load_osm, raster
from parse3mf import load

parts = load(sys.argv[1])
nodes, ways = load_osm(sys.argv[2])

# OSM building mask in metres, 1 m cells
EXT = (-450, 450, -320, 320)
RES = 1.0
osm_polys = [np.array([nodes[n] for n in w["nodes"]]) for w in ways if "building" in w.get("tags", {})]
osm_mask = raster(osm_polys, EXT, RES).astype(float)

# mesh building / non-building sample points (mm)
v, f = parts["3"]
mext = (100, 250, 111.58, 208.42)
mres = 0.25
mmask = raster(v[f][:, :, :2], mext, mres)
ys, xs = np.nonzero(np.ones_like(mmask))
pts = np.c_[mext[0] + (xs + 0.5) * mres, mext[2] + (ys + 0.5) * mres]
lab = mmask[ys, xs]
rng = np.random.default_rng(0)
pick = rng.choice(len(pts), 60000, replace=False)
pts, lab = pts[pick], lab[pick]
centre = np.array([(mext[0] + mext[1]) / 2, (mext[2] + mext[3]) / 2])


def apply(p, params):
    s, th, tx, ty = params
    c, sn = np.cos(th), np.sin(th)
    q = p - centre
    return s * np.c_[c * q[:, 0] - sn * q[:, 1], sn * q[:, 0] + c * q[:, 1]] + [tx, ty]


def score(params):
    q = apply(pts, params)
    ix = np.clip(((q[:, 0] - EXT[0]) / RES).astype(int), 0, osm_mask.shape[1] - 1)
    iy = np.clip(((q[:, 1] - EXT[2]) / RES).astype(int), 0, osm_mask.shape[0] - 1)
    m = osm_mask[iy, ix]
    return -(m[lab].mean() - m[~lab].mean())


best = None
for s in np.linspace(3.0, 7.0, 41):
    for tx in np.linspace(-80, 80, 17):
        for ty in np.linspace(-80, 80, 17):
            r = score((s, 0, tx, ty))
            if best is None or r < best[0]:
                best = (r, (s, 0, tx, ty))
print("grid", best)
res = minimize(score, best[1], method="Nelder-Mead",
               options={"xatol": 1e-4, "fatol": 1e-5, "initial_simplex": None, "maxiter": 4000})
print("refined", res.fun, res.x)
s, th, tx, ty = res.x
json.dump({"scale": s, "theta": th, "tx": tx, "ty": ty, "centre_mm": centre.tolist(), "score": -res.fun},
          open(sys.argv[3], "w"), indent=1)
