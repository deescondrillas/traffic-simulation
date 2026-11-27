#  Franco De Escondrillas ft. Claude Code · 2026-11-26

from __future__ import annotations

import bisect
import json
import math
import unicodedata
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

import numpy as np

from config import (
    DIVERGE_OFFSET, ETOILE_LANES, ETOILE_SPOKE_CLIP, ETOILE_TURN_OFFSET, HERMITE_MIN_POINTS,
    HERMITE_TANGENT, LOOP_TURN_TOLERANCE, MAX_HEADING_BREAK, MAX_POINT_GAP, MERGE_OFFSET, N_STREETS,
    OUTER_RING_CENTER, OUTER_RING_RADIUS, RESAMPLE_STEP, ROAD_GRAPH, SPIKE_COS, SPOKE_AVENUES,
    SPOKE_CLIP, SPOKE_RADIUS_BAND,
)

if TYPE_CHECKING:
    from agents.car_agent import CarAgent

MAC_MAHON = SPOKE_AVENUES.index("Avenue Mac-Mahon") + 1   # solo entra a la Étoile
MARCEAU = SPOKE_AVENUES.index("Avenue Marceau") + 1       # solo sale de la Étoile


def polar_angle(x: float, z: float) -> float:
    """Ángulo polar θ = atan2(−z, x), antihorario visto desde arriba."""
    return math.atan2(-z, x)


def wrap_angle(a: float | np.ndarray) -> float | np.ndarray:
    """Lleva un ángulo a [−π, π)."""
    return (a + np.pi) % (2 * np.pi) - np.pi


def avenue_key(avenue: str) -> str:
    """"Avenue des Champs-Élysées" → "elysees": id corto y sin acentos para los radios."""
    word = avenue.split()[-1].split("'")[-1]
    return unicodedata.normalize("NFKD", word).encode("ascii", "ignore").decode().lower().replace("-", "_")


def despike(points: np.ndarray, closed: bool = False) -> np.ndarray:
    """Quita los puntos donde la polilínea se regresa: los tramos OSM se traslapan en sus uniones."""
    pts = list(points)
    changed = True
    while changed and len(pts) > 3:
        changed = False
        out = [pts[0]]
        for i in range(1, len(pts) - 1):
            a, b = pts[i] - out[-1], pts[i + 1] - pts[i]
            na, nb = np.linalg.norm(a), np.linalg.norm(b)
            if na < 1e-3 or (nb > 1e-6 and np.dot(a, b) / (na * nb) < SPIKE_COS):
                changed = True
                continue
            out.append(pts[i])
        out.append(pts[-1])
        pts = out
    if closed and len(pts) > 3:
        a, b = pts[0] - pts[-1], pts[1] - pts[0]
        if np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b) + 1e-9) < SPIKE_COS:
            pts = pts[1:]
    return np.array(pts)


def resample(points: np.ndarray, step: float, closed: bool = False) -> np.ndarray:
    """Remuestrea una polilínea a puntos equiespaciados cada `step` metros."""
    points = despike(points, closed)
    if closed:
        points = np.vstack([points, points[:1]])
    seg = np.linalg.norm(np.diff(points, axis=0), axis=1)
    points = points[np.concatenate([[True], seg > 1e-6])]
    s = np.concatenate([[0.0], np.cumsum(np.linalg.norm(np.diff(points, axis=0), axis=1))])
    n = max(2, int(round(s[-1] / step)) + 1)
    targets = np.linspace(0.0, s[-1], n)
    if closed:
        targets = targets[:-1]   # el último coincide con el primero
    return np.column_stack([np.interp(targets, s, points[:, 0]), np.interp(targets, s, points[:, 1])])


def hermite(p0: np.ndarray, t0: np.ndarray, p1: np.ndarray, t1: np.ndarray) -> np.ndarray:
    """Curva de Hermite cúbica de p0 a p1 con tangentes unitarias t0, t1 (posición y rumbo continuos)."""
    chord = np.linalg.norm(p1 - p0)
    m0, m1 = t0 * chord * HERMITE_TANGENT, t1 * chord * HERMITE_TANGENT
    u = np.linspace(0.0, 1.0, max(HERMITE_MIN_POINTS, int(chord / RESAMPLE_STEP) * 2))[:, None]
    h00, h10 = 2 * u**3 - 3 * u**2 + 1, u**3 - 2 * u**2 + u
    h01, h11 = -2 * u**3 + 3 * u**2, u**3 - u**2
    return h00 * p0 + h10 * m0 + h01 * p1 + h11 * m1


def chain_segments(segments: list[dict]) -> np.ndarray:
    """Encadena tramos OSM por nodo; si no hay continuación, toma el tramo que empieza más cerca."""
    remaining = list(segments)
    current = remaining.pop(0)
    out = [current["xz"]]
    while remaining:
        nxt = next((g for g in remaining if g["from_node"] == current["to_node"]), None)
        if nxt is None:
            tail = out[-1][-1]
            nxt = min(remaining, key=lambda g: np.linalg.norm(g["xz"][0] - tail))
        remaining.remove(nxt)
        out.append(nxt["xz"])
        current = nxt
    return np.vstack(out)


@dataclass
class Lane:
    """Un carril: polilínea remuestreada en (x, z) más su topología."""

    id: str
    points: np.ndarray                  # (N, 2) en (x, z)
    loop: bool                          # True en las glorietas: s da la vuelta
    street: int | None = None           # radios: número de calle, 1..12
    exits: dict[int, tuple[float, str]] = field(default_factory=dict)  # calle -> (s de separación, id del radio)
    merges: list[tuple[float, str]] = field(default_factory=list)      # (s de incorporación, id del radio)
    end_lane: str | None = None         # radios: anillo al que se incorporan
    end_s: float = 0.0                  # radios: s de incorporación en ese anillo
    start_lane: str | None = None       # radios: anillo del que se separan
    start_s: float = 0.0
    stop_s: float = 0.0                 # radios: línea de ceda o de alto (donde empieza la curva final)
    avenue: str = ""
    left: str | None = None             # Étoile: carril hacia dentro
    right: str | None = None            # Étoile: carril hacia fuera

    def __post_init__(self) -> None:
        pts = np.vstack([self.points, self.points[:1]]) if self.loop else self.points
        d = np.diff(pts, axis=0)
        self.seg_len = np.linalg.norm(d, axis=1)
        self.s = np.concatenate([[0.0], np.cumsum(self.seg_len)])
        self.length = float(self.s[-1])
        self.heading = np.arctan2(-d[:, 1], d[:, 0])        # ψ de cada tramo
        dpsi = wrap_angle(np.diff(np.concatenate([self.heading, self.heading[:1]])))
        self.curvature = dpsi / np.maximum(self.seg_len, 1e-6)   # κ por tramo
        self.theta = np.arctan2(-pts[:, 1], pts[:, 0])
        self.radius = float(np.mean(np.hypot(self.points[:, 0], self.points[:, 1])))

    @property
    def tail_len(self) -> float:
        """Radios: largo de la curva final, de la línea de ceda/alto a la incorporación."""
        return self.length - self.stop_s


class RoadNetwork:
    """Arma la red desde `road_graph.json` y responde dónde está cada coche."""

    def __init__(self, path: str = ROAD_GRAPH) -> None:
        with open(path, encoding="utf-8") as f:
            raw = json.load(f)["lanes"]
        for lane in raw:
            lane["xz"] = np.array(lane["points"], dtype=float)[:, [0, 2]]
        self.lanes: dict[str, Lane] = {}
        self._build_etoile(raw)
        self._build_outer_ring()
        self._build_spokes(raw)
        for lane in self.lanes.values():
            lane.merges.sort()

    # --- construcción ---
    def _build_etoile(self, raw: list[dict]) -> None:
        for k in range(ETOILE_LANES):
            segs = [g for g in raw if g["roundabout"] and g["lane"] == k]
            pts = resample(chain_segments(segs), RESAMPLE_STEP, closed=True)
            self.lanes[f"etoile_{k}"] = Lane(f"etoile_{k}", pts, loop=True)
        for k in range(ETOILE_LANES):
            lane = self.lanes[f"etoile_{k}"]
            lane.left = f"etoile_{k + 1}" if k + 1 < ETOILE_LANES else None
            lane.right = f"etoile_{k - 1}" if k > 0 else None

    def _build_outer_ring(self) -> None:
        """Círculo antihorario ajustado a la calle dibujada (los tramos OSM se desvían hasta 3 m de ella)."""
        n = int(round(2 * np.pi * OUTER_RING_RADIUS / RESAMPLE_STEP))
        phi = np.linspace(0.0, 2 * np.pi, n, endpoint=False)
        cx, cz = OUTER_RING_CENTER
        pts = np.column_stack([cx + OUTER_RING_RADIUS * np.cos(phi), cz - OUTER_RING_RADIUS * np.sin(phi)])
        self.lanes["ring"] = Lane("ring", pts, loop=True)

    def _spoke_body(self, segs: list[dict], inbound: bool) -> np.ndarray:
        """Une los tramos de un sentido y los recorta entre los dos anillos."""
        segs = sorted(segs, key=lambda g: np.hypot(*g["xz"][0]), reverse=inbound)
        pts = resample(np.vstack([g["xz"] for g in segs]), RESAMPLE_STEP)
        r = np.hypot(pts[:, 0], pts[:, 1])
        th = np.arctan2(-pts[:, 1], pts[:, 0])
        r_in = np.array([self._radius_at("etoile_0", t) for t in th])
        r_out = np.array([self._radius_at("ring", t) for t in th])
        idx = np.flatnonzero((r > r_in + ETOILE_SPOKE_CLIP) & (r < r_out - SPOKE_CLIP))
        return pts[idx[0]: idx[-1] + 1]

    def _radius_at(self, lane_id: str, theta: float) -> float:
        lane = self.lanes[lane_id]
        i = int(np.argmin(np.abs(wrap_angle(lane.theta[:-1] - theta))))
        return float(np.hypot(*lane.points[i]))

    def _build_spokes(self, raw: list[dict]) -> None:
        for street, avenue in enumerate(SPOKE_AVENUES, start=1):
            segs = [g for g in raw if g["name"] == avenue and g["lane"] == 0 and g["highway"] != "service"]
            segs = [g for g in segs if self._crosses_band(g)]
            for inbound in (True, False):
                group = [g for g in segs if (np.hypot(*g["xz"][0]) > np.hypot(*g["xz"][-1])) == inbound]
                if not group:
                    continue
                body = self._spoke_body(group, inbound)
                src, dst = ("ring", "etoile_0") if inbound else ("etoile_0", "ring")
                lane_id = f"{avenue_key(avenue)}_{'in' if inbound else 'out'}"
                self._attach_spoke(lane_id, street, body, src, dst)

    @staticmethod
    def _crosses_band(g: dict) -> bool:
        r = np.hypot(g["xz"][:, 0], g["xz"][:, 1])
        return r.min() < SPOKE_RADIUS_BAND[1] and r.max() > SPOKE_RADIUS_BAND[0]

    def _attach_spoke(self, lane_id: str, street: int, body: np.ndarray, src: str, dst: str) -> None:
        """Alarga el radio con curvas: se separa de `src` y se incorpora a `dst`."""
        src_lane, dst_lane = self.lanes[src], self.lanes[dst]
        diverge = DIVERGE_OFFSET if src == "ring" else ETOILE_TURN_OFFSET
        merge = MERGE_OFFSET if dst == "ring" else ETOILE_TURN_OFFSET
        s_start = (self.closest_s(src, body[0]) - diverge) % src_lane.length
        s_end = (self.closest_s(dst, body[-1]) + merge) % dst_lane.length

        p0, psi0 = self._point_heading(src, s_start)
        p1, psi1 = self._point_heading(dst, s_end)
        tb0 = body[1] - body[0]
        tb1 = body[-1] - body[-2]
        head = hermite(p0, self._unit(psi0), body[0], tb0 / np.linalg.norm(tb0))
        tail = hermite(body[-1], tb1 / np.linalg.norm(tb1), p1, self._unit(psi1))
        pts_body = resample(np.vstack([head[:-1], body]), RESAMPLE_STEP)
        stop_s = float(np.sum(np.linalg.norm(np.diff(pts_body, axis=0), axis=1)))
        pts = resample(np.vstack([pts_body[:-1], tail]), RESAMPLE_STEP)

        self.lanes[lane_id] = Lane(lane_id, pts, loop=False, end_lane=dst, end_s=s_end, start_lane=src,
                                   start_s=s_start, stop_s=stop_s, avenue=SPOKE_AVENUES[street - 1],
                                   street=street)
        src_lane.exits[street] = (s_start, lane_id)
        dst_lane.merges.append((s_end, lane_id))

    @staticmethod
    def _unit(psi: float) -> np.ndarray:
        return np.array([math.cos(psi), -math.sin(psi)])   # (dx, dz) con ψ = atan2(−dz, dx)

    def _point_heading(self, lane_id: str, s: float) -> tuple[np.ndarray, float]:
        x, z, psi, _ = self.pose(lane_id, s)
        return np.array([x, z]), psi

    # --- consultas ---
    def closest_s(self, lane_id: str, p: np.ndarray) -> float:
        lane = self.lanes[lane_id]
        return float(lane.s[int(np.argmin(np.linalg.norm(lane.points - p, axis=1)))])

    def pose(self, lane_id: str, s: float) -> tuple[float, float, float, float]:
        """(x, z, ψ, κ) en la posición `s` del carril, por interpolación lineal."""
        lane = self.lanes[lane_id]
        if lane.loop:
            s %= lane.length
        s = min(max(s, 0.0), lane.length - 1e-9)
        i = min(int(np.searchsorted(lane.s, s, side="right")) - 1, len(lane.seg_len) - 1)
        u = (s - lane.s[i]) / max(lane.seg_len[i], 1e-9)
        a = lane.points[i]
        b = lane.points[(i + 1) % len(lane.points)] if lane.loop else lane.points[i + 1]
        p = a + u * (b - a)
        return float(p[0]), float(p[1]), float(lane.heading[i]), float(lane.curvature[i])

    def theta_at(self, lane_id: str, s: float) -> float:
        x, z, _, _ = self.pose(lane_id, s)
        return polar_angle(x, z)

    def s_at_angle(self, lane_id: str, theta: float) -> float:
        """Glorietas: s del carril en el ángulo polar θ (para cambiar de carril)."""
        lane = self.lanes[lane_id]
        return float(lane.s[int(np.argmin(np.abs(wrap_angle(lane.theta[:-1] - theta))))])

    def has_exit(self, lane_id: str, street: int) -> bool:
        """¿Esa calle tiene salida desde esta glorieta ("etoile_0" o "ring")?"""
        return street in self.lanes[lane_id].exits

    def spokes(self, kind: str) -> list[str]:
        """Ids de los radios "in" (hacia la Étoile) o "out" (hacia el anillo exterior)."""
        return sorted(k for k in self.lanes if k.endswith(f"_{kind}"))

    def plot(self, ax=None, color: str = "0.75"):
        """Vista superior para depurar: −Z (norte) hacia arriba."""
        import matplotlib.pyplot as plt   # solo para depurar; la simulación no lo necesita

        ax = ax or plt.subplots(figsize=(7, 7))[1]
        for lane in self.lanes.values():
            pts = np.vstack([lane.points, lane.points[:1]]) if lane.loop else lane.points
            ax.plot(pts[:, 0], -pts[:, 1], color=color, lw=1.0, zorder=0)
        ax.set_aspect("equal")
        ax.set_xlabel("x (m, este)")
        ax.set_ylabel("−z (m, norte)")
        return ax


class LaneIndex:
    """Coches de un carril ordenados por s. `ahead` y `window` respetan la vuelta de las glorietas."""

    def __init__(self, lane: Lane) -> None:
        self.lane = lane
        self.s: list[float] = []
        self.cars: list[CarAgent] = []

    def add(self, s: float, car: CarAgent) -> None:
        i = bisect.bisect_left(self.s, s)
        self.s.insert(i, s)
        self.cars.insert(i, car)

    def remove(self, car: CarAgent) -> None:
        for i, c in enumerate(self.cars):
            if c is car:
                del self.s[i], self.cars[i]
                return

    def ahead(self, s: float, exclude: CarAgent | None, max_dist: float) -> tuple[float, CarAgent | None]:
        """(distancia, coche) del siguiente coche adelante, o (inf, None)."""
        n = len(self.s)
        i = bisect.bisect_right(self.s, s)
        for k in range(n):
            j = i + k
            if j >= n:
                if not self.lane.loop:
                    break
                j -= n
            car = self.cars[j]
            if car is exclude:
                continue
            d = self.s[j] - s
            if self.lane.loop:
                d %= self.lane.length
            if d > max_dist:
                break
            return d, car
        return math.inf, None

    def window(self, s0: float, s1: float, exclude: CarAgent | None = None) -> bool:
        """True si algún coche (distinto de `exclude`) está entre s0 y s1."""
        for s, car in zip(self.s, self.cars):
            if car is exclude:
                continue
            if self.lane.loop:
                if (s - s0) % self.lane.length <= (s1 - s0) % self.lane.length:
                    return True
            elif s0 <= s <= s1:
                return True
        return False


def check_network(net: RoadNetwork) -> None:
    """Comprobaciones de la sección 5.6 de Plan&rules.md."""
    etoile = [k for k in net.lanes if k.startswith("etoile_")]
    assert len(etoile) == ETOILE_LANES and "ring" in net.lanes, "faltan anillos"
    assert len(net.spokes("in")) == 11 and len(net.spokes("out")) == 11, (net.spokes("in"), net.spokes("out"))
    for sid in net.spokes("in") + net.spokes("out"):
        lane = net.lanes[sid]
        assert {lane.start_lane, lane.end_lane} == {"ring", "etoile_0"}, sid
    worst_gap, worst_break = 0.0, 0.0
    for lane in net.lanes.values():
        worst_gap = max(worst_gap, float(lane.seg_len.max()))
        worst_break = max(worst_break, float(np.abs(wrap_angle(np.diff(lane.heading))).max()))
        if lane.loop:
            total = float(np.sum(wrap_angle(np.diff(np.concatenate([lane.heading, lane.heading[:1]])))))
            assert abs(total - 2 * np.pi) < LOOP_TURN_TOLERANCE, (lane.id, math.degrees(total))
    assert worst_gap <= MAX_POINT_GAP, worst_gap
    assert worst_break <= MAX_HEADING_BREAK, math.degrees(worst_break)
    assert set(net.lanes["etoile_0"].exits) == set(range(1, N_STREETS + 1)) - {MAC_MAHON}, "Mac-Mahon no sale de la Étoile"
    assert set(net.lanes["ring"].exits) == set(range(1, N_STREETS + 1)) - {MARCEAU}, "Marceau no entra a la Étoile"
    print(f"OK · salto máximo {worst_gap:.2f} m · quiebre máximo {math.degrees(worst_break):.1f}°")
    for k in etoile + ["ring"]:
        lane = net.lanes[k]
        print(f"  {k:9s} L = {lane.length:6.1f} m  R ≈ {lane.radius:5.1f} m  "
              f"salidas = {len(lane.exits):2d}  incorporaciones = {len(lane.merges):2d}")


if __name__ == "__main__":
    import matplotlib.pyplot as plt

    network = RoadNetwork()
    check_network(network)
    ax = network.plot()
    for sid in network.spokes("in") + network.spokes("out"):
        x, z, _, _ = network.pose(sid, network.lanes[sid].stop_s)
        ax.plot(x, -z, "o", ms=3, color="tab:red" if sid.endswith("_in") else "tab:blue")
    ax.set_title("Red vial: radios entrantes (rojo) y salientes (azul), en su línea de ceda/alto")
    plt.show()
