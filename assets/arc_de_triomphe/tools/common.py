#  Franco De Escondrillas ft. Claude Code · 2026-11-09
"""Shared helpers: OSM loading/projection and 2D rasterisation."""
import json

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.collections import PolyCollection
from pyproj import Transformer

ARC_LATLON = (48.873792, 2.295028)
_to_local = Transformer.from_crs(
    "EPSG:4326", f"+proj=aeqd +lat_0={ARC_LATLON[0]} +lon_0={ARC_LATLON[1]} +units=m", always_xy=True)


def load_osm(path):
    """Return (nodes {id: (x, y) metres east/north of the Arc}, ways list)."""
    els = json.load(open(path))["elements"]
    ids = [e["id"] for e in els if e["type"] == "node"]
    lon = [e["lon"] for e in els if e["type"] == "node"]
    lat = [e["lat"] for e in els if e["type"] == "node"]
    x, y = _to_local.transform(lon, lat)
    nodes = dict(zip(ids, zip(x, y)))
    ways = [e for e in els if e["type"] == "way"]
    return nodes, ways


def raster(polys, extent, res):
    """Rasterise a list of Nx2 polygons; extent=(x0, x1, y0, y1), returns bool array [row=y, col=x]."""
    x0, x1, y0, y1 = extent
    w, h = int(round((x1 - x0) / res)), int(round((y1 - y0) / res))
    fig = plt.figure(figsize=(w / 100, h / 100), dpi=100)
    ax = fig.add_axes([0, 0, 1, 1]); ax.axis("off")
    ax.add_collection(PolyCollection(polys, facecolors="k", edgecolors="k", linewidths=0.3, antialiased=False))
    ax.set_xlim(x0, x1); ax.set_ylim(y0, y1)
    fig.canvas.draw()
    img = np.asarray(fig.canvas.buffer_rgba())[::-1, :, 0] < 128
    plt.close(fig)
    return img
