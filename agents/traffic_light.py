#  Franco De Escondrillas ft. Claude Code · 2026-11-26
"""TrafficLightAgent: semáforo BDI en cada incorporación de un radio saliente al anillo exterior.

- Creencias: colas por fase, a partir de los INFORM de los coches en la zona de aproximación.
- Deliberación: reparte `CYCLE_TIME` de verde con el valor de Shapley de las dos fases.
- Plan: verde → verde parpadeante → amarillo → la otra fase. `RING` es la fase por defecto.

`TrafficLight` es solo la cabeza que se dibuja: el agente la actualiza y el renderizador la lee.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import pi, radians

import agentpy as ap

from agents.game_theory import Inform, green_split
from config import (
    BLINK_TIME, CYCLE_TIME, IDM_B, MAX_EXTENSION, MIN_GREEN, SIM_DT, TRAFFIC_LIGHTS, YELLOW_TIME,
)

RING, MERGE = "RING", "MERGE"
PHASES = (RING, MERGE)
GREEN_STATES = ("green", "blinking_green")


@dataclass
class TrafficLight:
    """Cabeza de un semáforo en una aproximación al anillo exterior.

    `approach` es "ring" (el anillo antes del cruce), "merge" (el radio que sale de la Étoile)
    u "outside" (la avenida que llega desde fuera del mapa; el sistema es cerrado y nadie la usa).
    """

    avenue: str
    approach: str
    x: float
    z: float
    yaw: float                  # rad, giro del modelo alrededor de Y para que los focos miren al tráfico
    state: str = "red"
    state_time: float = 0.0     # s en el estado actual, para el parpadeo

    def set_state(self, state: str) -> None:
        if state != self.state:
            self.state = state
            self.state_time = 0.0


def intersection_heads() -> dict[str, dict[str, TrafficLight]]:
    """Cabezas de `TRAFFIC_LIGHTS` agrupadas por avenida y aproximación."""
    heads: dict[str, dict[str, TrafficLight]] = {}
    for avenue, approach, x, z, heading in TRAFFIC_LIGHTS:
        heads.setdefault(avenue, {})[approach] = TrafficLight(avenue, approach, x, z, radians(heading) - pi / 2)
    return heads


class TrafficLightAgent(ap.Agent):
    """Semáforo BDI de un cruce: fase `RING` (pasa el anillo) y `MERGE` (se incorpora el radio)."""

    def setup(self) -> None:
        self.spoke_id = ""
        self.avenue = ""
        self.ring_stop_s = 0.0
        self.heads: dict[str, TrafficLight] = {}
        self.phase = RING
        self.sub = "green"                  # green, blinking_green o yellow de la fase activa
        self.timer = 0.0
        self.inbox: list[Inform] = []
        self.queues = {RING: 0, MERGE: 0}
        self.budget = {RING: CYCLE_TIME, MERGE: MIN_GREEN}
        self.max_queue = 0

    def receive(self, msg: Inform) -> None:
        self.inbox.append(msg)

    def head(self, phase: str) -> str:
        """Estado de la luz que ve cada fase."""
        return self.sub if phase == self.phase else "red"

    def allows(self, phase: str, dist_stop: float, v: float) -> bool:
        """¿Puede seguir un coche a `dist_stop` de la línea? En amarillo sigue solo si ya no alcanza a frenar."""
        state = self.head(phase)
        if state in GREEN_STATES:
            return True
        if state == "yellow":
            return dist_stop < v * v / (2 * IDM_B)
        return False

    # --- ciclo BDI ---
    def perceive(self) -> None:
        self.queues = {RING: 0, MERGE: 0}
        for msg in self.inbox:
            self.queues[msg.content["phase"]] += 1
        self.inbox = []
        self.max_queue = max(self.max_queue, self.queues[MERGE])

    def deliberate(self) -> None:
        _, share = green_split(self.queues, default=RING)
        for p in PHASES:
            self.budget[p] = max(MIN_GREEN, CYCLE_TIME * share[p])

    def wants_switch(self) -> bool:
        other = MERGE if self.phase == RING else RING
        if self.timer < MIN_GREEN:
            return False
        if self.queues[MERGE] == 0:
            return self.phase == MERGE          # el anillo es la fase por defecto
        extension = MAX_EXTENSION if self.queues[self.phase] > 0 else 0.0
        if self.timer >= self.budget[self.phase] + extension:
            return True
        return self.timer >= self.budget[self.phase] and self.queues[self.phase] == 0 and self.queues[other] > 0

    def act(self) -> None:
        self.timer += SIM_DT
        if self.sub == "green" and self.wants_switch():
            self.sub, self.timer = "blinking_green", 0.0
        elif self.sub == "blinking_green" and self.timer >= BLINK_TIME:
            self.sub, self.timer = "yellow", 0.0
        elif self.sub == "yellow" and self.timer >= YELLOW_TIME:
            self.phase = MERGE if self.phase == RING else RING
            self.sub, self.timer = "green", 0.0
        self.sync_heads()

    def step(self) -> None:
        self.perceive()
        self.deliberate()
        self.act()

    def sync_heads(self) -> None:
        """La avenida de fuera copia al radio que se incorpora, aunque no traiga coches."""
        states = {"ring": self.head(RING), "merge": self.head(MERGE), "outside": self.head(MERGE)}
        for approach, head in self.heads.items():
            head.set_state(states[approach])
