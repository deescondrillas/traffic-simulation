#  Franco De Escondrillas ft. Claude Code · 2026-11-26
"""CarAgent: coche reactivo con máquina de estados, IDM, destinos por calle y juego de dos roles.

DRIVING ⇄ YIELDING        encuentro en la Étoile (frena, o lo detiene la regla contra el atasco)
DRIVING ⇄ STOPPED         semáforo en amarillo o rojo en el anillo exterior
DRIVING ⇄ CHANGING_LANE   solo en la Étoile
"""

from __future__ import annotations

import math
import random

import agentpy as ap
import numpy as np

from agents.game_theory import ROLE_A, ROLE_B, Inform
from config import (
    APPROACH_DIST, CAR_LENGTH, DECISION_DIST, EXIT_SPACE, GAP_BACK, GAP_FRONT, IDM_A, IDM_B, IDM_DELTA,
    IDM_S0, IDM_T, LANE_BY_STREETS, LANE_CHANGE_ARC, LANE_CHANGE_TIME, LOOKAHEAD, MAX_SPEED, MIN_GAP,
    MIN_RIVAL_DIST, N_STREETS, SIM_DT, STOP_EPS, T_CONFLICT, WHEELBASE, YIELD_TIMEOUT,
)
from environment.road_network import Lane, RoadNetwork, polar_angle

DRIVING, YIELDING, STOPPED, CHANGING_LANE = "DRIVING", "YIELDING", "STOPPED", "CHANGING_LANE"
STATES = (DRIVING, YIELDING, STOPPED, CHANGING_LANE)


def idm_acceleration(v: float, gap: float, v_lead: float) -> float:
    """IDM: acelera hacia MAX_SPEED y frena según la distancia y la diferencia de velocidad con el de adelante."""
    free = 1.0 - (v / MAX_SPEED) ** IDM_DELTA
    if math.isinf(gap):
        return IDM_A * free
    s_star = IDM_S0 + max(0.0, v * IDM_T + v * (v - v_lead) / (2 * math.sqrt(IDM_A * IDM_B)))
    return IDM_A * (free - (s_star / max(gap, 0.01)) ** 2)


class CarAgent(ap.Agent):
    """Coche persistente: va de calle en calle y aprende solo de sus propios encuentros."""

    def setup(self) -> None:
        self.lane_id = ""
        self.s = 0.0
        self.v = 0.0
        self.state = DRIVING
        self.street = 0                      # calle actual (o la última, si va por una glorieta)
        self.dest = 0                        # calle a la que va en este tramo
        self.goal = 0                        # calle destino; difiere de `dest` si se desvía por la Étoile
        self.journey_start = 0.0
        self.journey_streets = 0             # calles en sentido antihorario hasta `goal` al sortearla
        self.route = ""                      # "etoile", "ring" o "detour" (anillo → Étoile)
        self.target_lane = 0
        self.crossed = False                 # ya cruzó la línea de ceda/alto de su radio
        self.may_cross = True
        self.encounter: dict | None = None   # juego en curso (como A)
        self.yield_line: tuple[float, CarAgent, float] | None = None  # cede como B: (s, A, desde cuándo)
        self.change_timer = 0.0
        self.prev_lane: str | None = None    # carril anterior, para mezclar la pose al cambiar de carril
        self.laps = 0
        self.counts = np.ones((2, 2))        # counts[rol][acción que ha visto del rival]
        self.odometer = 0.0                  # m recorridos, para que giren las llantas
        self.trip_start: float | None = None
        self.trip_wait = 0.0
        self._gap = math.inf
        # Tono de la carrocería en vueltas (0..1) desde el rojo, solo para distinguirlo en pantalla.
        # Usa `random` y no `self.model.random` para no alterar la secuencia de la simulación.
        self.hue = random.random()

    # --- utilidades ---
    @property
    def net(self) -> RoadNetwork:
        return self.model.network

    @property
    def lane(self) -> Lane:
        return self.net.lanes[self.lane_id]

    @property
    def etoile_k(self) -> int | None:
        return int(self.lane_id[-1]) if self.lane_id.startswith("etoile_") else None

    def projected_s(self) -> float:
        """s en el anillo al que se incorpora (solo radios)."""
        return self.lane.end_s - (self.lane.length - self.s)

    def exit_from(self, ring: str) -> str:
        """Radio por el que se llega a la calle destino desde una glorieta."""
        return self.net.lanes[ring].exits[self.dest][1]

    @property
    def exit_id(self) -> str | None:
        """Radio por el que saldrá de la glorieta en la que va (None si va por un radio)."""
        if not self.lane.loop:
            return None
        return self.exit_from("ring" if self.lane_id == "ring" else "etoile_0")

    def exit_s(self) -> float | None:
        exit_id = self.exit_id
        return None if exit_id is None else self.net.lanes[exit_id].start_s

    def remaining_angle(self) -> float:
        """Ángulo polar que falta hasta la salida elegida en la Étoile (0..2π)."""
        theta_exit = self.net.theta_at("etoile_0", self.exit_s())
        theta = self.net.theta_at(self.lane_id, self.s)
        return float((theta_exit - theta) % (2 * np.pi))

    def roll_street(self, ring: str) -> int:
        """Siguiente calle destino: se repite el tiro si es la actual o no tiene salida desde `ring`."""
        while True:
            street = self.model.random.randint(1, N_STREETS)
            if street != self.street and self.net.has_exit(ring, street):
                return street

    def plan_detour(self) -> None:
        """Destino lejano por el anillo exterior: va a la siguiente calle que entra y cruza por la Étoile.

        Mac-Mahon no tiene salida desde la Étoile, así que a ella siempre se llega por el anillo.
        """
        limit = self.model.detour
        if limit is None or self.journey_streets <= limit or not self.net.has_exit("etoile_0", self.goal):
            return
        via = next(st for k in (1, 2)
                   if self.net.has_exit("ring", st := (self.street + k - 1) % N_STREETS + 1))
        self.dest, self.route = via, "detour"

    def receive(self, msg: Inform) -> None:
        """INFORM de otro coche: lo que hizo en el encuentro → un conteo más en el rol propio."""
        if msg.topic == "merge_action":
            own_role = ROLE_B if msg.content["role"] == ROLE_A else ROLE_A
            self.counts[own_role, msg.content["action"]] += 1

    # --- entrar a un carril ---
    def enter_lane(self, lane_id: str, s: float) -> None:
        prev = self.lane_id
        self.lane_id, self.s, self.crossed = lane_id, s, False
        self.change_timer = 0.0                          # un cambio de carril termina al salir de la glorieta
        lane = self.lane
        if not lane.loop:                                # llega a una calle: tira la siguiente
            if prev:
                self.model.finish_trip(self, "ring" if prev == "ring" else "etoile")
            self.street = lane.street
            if self.goal and self.street == self.goal:   # en un desvío, la calle intermedia no cuenta
                self.model.finish_journey(self)
                self.goal = 0
            if not self.goal:
                self.goal = self.roll_street(lane.end_lane)
                self.journey_start = self.model.time
                self.journey_streets = (self.goal - self.street) % N_STREETS
                self.route = "ring" if lane.end_lane == "ring" else "etoile"
            self.dest = self.goal
            if lane.end_lane == "ring":
                self.plan_detour()
            self.trip_start, self.trip_wait = self.model.time, 0.0
        elif lane_id == "etoile_0" and prev.endswith("_in"):
            self.laps = 0
            self.target_lane = sum((self.dest - self.street) % N_STREETS >= cut for cut in LANE_BY_STREETS)

    # --- decidir (con la foto del inicio del paso) ---
    def decide(self) -> None:
        if self.change_timer > 0:
            self.change_timer = max(0.0, self.change_timer - SIM_DT)

        # coche de la glorieta que cede: la línea de ceda dura hasta que el entrante cruza
        if self.yield_line is not None:
            _, entrant, since = self.yield_line
            e = entrant.encounter
            if (entrant.crossed or e is None or e["rival"] is not self or e["winner"] == ROLE_B
                    or self.model.time - since > YIELD_TIMEOUT):
                self.yield_line = None

        if not self.lane.loop and not self.crossed:
            self.may_cross = self.decide_crossing()
        if self.etoile_k is not None:
            self.lane_change()

        gap, v_lead, constraint = self.binding_gap()
        a = idm_acceleration(self.v, gap, v_lead)
        self.v = max(0.0, min(MAX_SPEED, self.v + a * SIM_DT))
        self._gap = gap

        if self.change_timer > 0:
            self.state = CHANGING_LANE
        elif constraint in (YIELDING, STOPPED) and gap < LOOKAHEAD:
            self.state = constraint
        else:
            self.state = DRIVING
        self.send_approach_inform()

    def decide_crossing(self) -> bool:
        """¿Puede cruzar la línea de ceda/alto de su radio? Juego en la Étoile, semáforo en el anillo."""
        lane = self.lane
        dist_stop = lane.stop_s - self.s
        end_idx = self.model.index[lane.end_lane]
        front = lane.end_s + CAR_LENGTH + MIN_GAP

        if lane.end_lane == "ring":                       # radio saliente: manda el semáforo
            light = self.model.light_of[self.lane_id]
            blocked = end_idx.window(lane.end_s - lane.tail_len - CAR_LENGTH, front, exclude=self)
            return light.allows("MERGE", dist_stop, self.v) and not blocked

        if dist_stop > DECISION_DIST or not self.is_first():   # todavía no decide: se acerca
            self.encounter = None
            return True
        # regla contra el atasco total: sin espacio en el radio de salida, está obligado a ceder
        exit_id = self.exit_from("etoile_0")
        exit_idx, exit_lane = self.model.index[exit_id], self.net.lanes[exit_id]
        if (exit_idx.window(0.0, EXIT_SPACE)
                or len(exit_idx.cars) * (CAR_LENGTH + IDM_S0) > exit_lane.length - EXIT_SPACE):
            self.encounter = None
            return False

        if self.encounter is not None and not self.rival_coming():
            self.encounter = None                         # el rival ya pasó, salió o cambió de carril
        e = self.encounter
        waiting_rival = e["rival"] if e is not None and e["winner"] != ROLE_B else None
        blocked = end_idx.window(lane.end_s - lane.tail_len - MIN_RIVAL_DIST, front, exclude=waiting_rival)
        if e is None:
            if blocked:
                return False
            rival = self.find_rival()
            if rival is None:
                return True
            e = self.encounter = self.model.start_encounter(self, rival)
        elif e["winner"] == ROLE_A and e["rival"].yield_line is None:
            e["winner"] = ROLE_B                          # B se cansó de esperar
        elif e["winner"] is None and self.model.time >= e["retry_at"]:
            self.model.play_merge(self)
        return e["winner"] == ROLE_A and not blocked

    def is_first(self) -> bool:
        """¿Es el primero de su radio que aún no cruza la línea?"""
        return not any(c is not self and not c.crossed and c.s > self.s for c in self.model.index[self.lane_id].cars)

    def rival_coming(self) -> bool:
        """¿El rival sigue en el carril 0 y aún no llega al punto de incorporación?"""
        rival = self.encounter["rival"]
        ring_len = self.net.lanes["etoile_0"].length
        return rival.lane_id == "etoile_0" and (self.lane.end_s - rival.s) % ring_len < ring_len / 2

    def find_rival(self) -> CarAgent | None:
        """B: el coche del carril 0 que llegará al punto de incorporación en menos de T_CONFLICT s."""
        lane = self.lane
        ring = self.net.lanes["etoile_0"]
        idx = self.model.index["etoile_0"]
        best, best_t = None, math.inf
        for s, car in zip(idx.s, idx.cars):
            if car.lane_id != "etoile_0":
                continue                                   # proyección de otro entrante
            d = (lane.end_s - s) % ring.length
            if d < lane.tail_len + MIN_RIVAL_DIST or d > MAX_SPEED * T_CONFLICT + lane.tail_len + MIN_RIVAL_DIST:
                continue
            ex = car.exit_s()
            if ex is not None and (ex - s) % ring.length < d:
                continue                                   # sale antes de llegar
            t = d / max(car.v, 0.1)
            if t < T_CONFLICT and t < best_t:
                best, best_t = car, t
        return best

    def lane_change(self) -> None:
        """Un carril a la vez hacia el objetivo; reserva LANE_CHANGE_ARC por carril para volver al 0."""
        k = self.etoile_k
        if self.change_timer > 0:
            return
        rem = self.remaining_angle()
        if k > 0 and rem <= k * LANE_CHANGE_ARC:
            dest = f"etoile_{k - 1}"
        elif k < self.target_lane and rem > (k + 1) * LANE_CHANGE_ARC:
            dest = f"etoile_{k + 1}"
        else:
            return
        s_new = self.net.s_at_angle(dest, self.net.theta_at(self.lane_id, self.s))
        dest_idx = self.model.index[dest]
        if dest_idx.window(s_new - GAP_BACK, s_new + GAP_FRONT, exclude=self):
            return
        self.model.index[self.lane_id].remove(self)
        self.prev_lane = self.lane_id
        self.lane_id, self.s = dest, s_new
        dest_idx.add(s_new, self)
        self.change_timer = LANE_CHANGE_TIME

    def binding_gap(self) -> tuple[float, float, str]:
        """(distancia, velocidad del líder, restricción) más restrictiva hacia adelante."""
        lane = self.lane
        idx = self.model.index
        best = (math.inf, MAX_SPEED, DRIVING)

        def consider(gap: float, v_lead: float, kind: str) -> None:
            nonlocal best
            if gap < best[0]:
                best = (gap, v_lead, kind)

        if lane.loop:
            d, car = idx[self.lane_id].ahead(self.s, self, LOOKAHEAD)
            exits_here = self.exit_id is not None and self.net.lanes[self.exit_id].start_lane == self.lane_id
            d_exit = (self.exit_s() - self.s) % lane.length if exits_here else math.inf
            if car is not None and d <= d_exit + CAR_LENGTH:
                consider(d - CAR_LENGTH, car.v, DRIVING)
            if d_exit < LOOKAHEAD:
                d2, car2 = idx[self.exit_id].ahead(-1e-9, self, LOOKAHEAD - d_exit)
                if car2 is not None:
                    consider(d_exit + d2 - CAR_LENGTH, car2.v, DRIVING)
            if self.lane_id == "ring":                     # semáforos del anillo
                light, d_stop = self.model.next_ring_light(self.s)
                if (light is not None and d_stop < min(LOOKAHEAD, d_exit)
                        and not light.allows("RING", d_stop, self.v)):
                    consider(d_stop, 0.0, STOPPED)
            if self.yield_line is not None:
                d_y = (self.yield_line[0] - self.s) % lane.length
                if d_y < LOOKAHEAD:
                    consider(d_y, 0.0, YIELDING)
        else:
            d, car = idx[self.lane_id].ahead(self.s, self, LOOKAHEAD)
            if car is not None:
                consider(d - CAR_LENGTH, car.v, DRIVING)
            if not self.crossed and not self.may_cross:
                consider(lane.stop_s - self.s, 0.0, STOPPED if lane.end_lane == "ring" else YIELDING)
            elif self.crossed:                             # en la curva final: ya cuenta el anillo
                end_len = self.net.lanes[lane.end_lane].length
                d2, car2 = idx[lane.end_lane].ahead(self.projected_s() % end_len, self, LOOKAHEAD)
                if car2 is not None:                       # adelante de su proyección
                    consider(d2 - CAR_LENGTH, car2.v, DRIVING)
        return best

    def send_approach_inform(self) -> None:
        """INFORM al semáforo: posición y velocidad dentro de su zona de aproximación."""
        if self.lane_id == "ring":
            light, d_stop = self.model.next_ring_light(self.s)
            if light is not None and d_stop < APPROACH_DIST:
                light.receive(Inform(self.id, "approach", {"phase": "RING", "dist": d_stop, "v": self.v}))
        elif self.lane_id.endswith("_out") and not self.crossed:
            d_stop = self.lane.stop_s - self.s
            if d_stop < APPROACH_DIST:
                self.model.light_of[self.lane_id].receive(
                    Inform(self.id, "approach", {"phase": "MERGE", "dist": d_stop, "v": self.v}))

    # --- moverse ---
    def move(self) -> None:
        ds = self.v * SIM_DT
        if ds > self._gap - MIN_GAP:                       # frena de golpe: nunca hay traslapes
            ds = max(0.0, self._gap - MIN_GAP)
            self.v = ds / SIM_DT
        self.odometer += ds
        if self.trip_start is not None and self.v < STOP_EPS:
            self.trip_wait += SIM_DT
        lane = self.lane
        s_old, s_new = self.s, self.s + ds

        if not lane.loop:
            if not self.crossed and s_new >= lane.stop_s and self.may_cross:
                self.crossed = True
                self.encounter = None
            if s_new >= lane.length:
                end_len = self.net.lanes[lane.end_lane].length
                self.enter_lane(lane.end_lane, (lane.end_s + s_new - lane.length) % end_len)
            else:
                self.s = s_new
            return

        # glorieta: ¿pasa por su salida?
        ex = self.exit_s()
        if ex is not None and self.net.lanes[self.exit_id].start_lane == self.lane_id:
            d_exit = (ex - s_old) % lane.length
            if d_exit <= ds:
                self.enter_lane(self.exit_id, ds - d_exit)
                return
        if self.etoile_k is not None and self.etoile_k > 0:
            before = self.remaining_angle()
            self.s = s_new % lane.length
            if self.remaining_angle() > before + np.pi:    # se pasó de su salida: otra vuelta
                self.laps += 1
            return
        self.s = s_new % lane.length

    # --- dibujo (solo lectura) ---
    def render_pose(self) -> tuple[float, float, float, float]:
        """(x, z, ψ, δ): posición, rumbo y ángulo de las llantas delanteras, δ = atan(L·κ).

        Durante un cambio de carril mezcla linealmente la pose del carril anterior con la nueva.
        """
        x, z, psi, kappa = self.net.pose(self.lane_id, self.s)
        if self.change_timer > 0 and self.prev_lane:
            theta = polar_angle(x, z)
            xo, zo, psi_o, _ = self.net.pose(self.prev_lane, self.net.s_at_angle(self.prev_lane, theta))
            u = self.change_timer / LANE_CHANGE_TIME       # 1 → todavía en el carril anterior
            x, z = u * xo + (1 - u) * x, u * zo + (1 - u) * z
            psi = psi + u * math.atan2(math.sin(psi_o - psi), math.cos(psi_o - psi))
        return x, z, psi, math.atan(WHEELBASE * kappa)
