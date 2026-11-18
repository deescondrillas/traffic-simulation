#  Franco De Escondrillas ft. Claude Code · 2026-11-09
"""Read a Bambu/map2model 3MF into per-part numpy meshes (world coords, mm, Z-up)."""
import sys
import zipfile
import xml.etree.ElementTree as ET

import numpy as np

NS = {"m": "http://schemas.microsoft.com/3dmanufacturing/core/2015/02"}


def _affine(s):
    v = list(map(float, s.split()))
    m = np.eye(4)
    m[:3, :3] = np.array(v[:9]).reshape(3, 3)  # 3MF rows are basis vectors
    m[3, :3] = v[9:12]
    return m


def load(path):
    with zipfile.ZipFile(path) as z:
        root = ET.fromstring(z.read("3D/3dmodel.model"))
    meshes, comps = {}, {}
    for obj in root.iterfind("m:resources/m:object", NS):
        oid = obj.get("id")
        mesh = obj.find("m:mesh", NS)
        if mesh is not None:
            v = np.array([[float(e.get(k)) for k in "xyz"] for e in mesh.iterfind("m:vertices/m:vertex", NS)])
            f = np.array([[int(e.get(k)) for k in ("v1", "v2", "v3")] for e in mesh.iterfind("m:triangles/m:triangle", NS)])
            meshes[oid] = (v, f)
        c = obj.find("m:components", NS)
        if c is not None:
            comps[oid] = [(e.get("objectid"), _affine(e.get("transform"))) for e in c.iterfind("m:component", NS)]
    parts = {}
    for item in root.iterfind("m:build/m:item", NS):
        top = _affine(item.get("transform"))
        for oid, m in comps.get(item.get("objectid"), [(item.get("objectid"), np.eye(4))]):
            v, f = meshes[oid]
            vh = np.c_[v, np.ones(len(v))] @ (m @ top)
            parts[oid] = (vh[:, :3], f)
    return parts


if __name__ == "__main__":
    for k, (v, f) in load(sys.argv[1]).items():
        print(k, len(v), len(f), v.min(0).round(2), v.max(0).round(2))
