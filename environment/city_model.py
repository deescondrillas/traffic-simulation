# A01739410 – Franco De Escondrillas
# A01739769 – Enrique Jiménez
# 2026-11-30

"""CityModel: la ciudad de AgentPy con su red vial, coches persistentes y semáforos BDI.

Orden de cada paso: semáforos (BDI) → foto de los carriles → cada coche decide → cada coche se mueve.
El modelo también arbitra los encuentros de la Étoile y corre el curso de manejo (`warmup`).
"""

from config import (
    CAR_LENGTH, ETOILE_DETOUR, ETOILE_LANES, LIGHT_STOP_BACK, N_CARS, RETRY_TIME, SEED, SIM_DT, SPAWN_MARGIN,
    SPAWN_SPACING, START_SPEED, YIELD_BACK, YIELD_DECEL,
)
from agents.traffic_light import TrafficLight, TrafficLightAgent, intersection_heads
from agents.game_theory import C, D, OUTCOMES, ROLE_A, ROLE_B, Inform, belief, play
from environment.road_network import LaneIndex, RoadNetwork
from agents.car_agent import STATES, CarAgent
from dataclasses import dataclass
from collections import Counter
from pathlib import Path
import agentpy as ap
import numpy as np
import json
import math


@dataclass
class SchoolLog:
    """Bitácora del curso de manejo. NaN = ese coche no jugó ese rol en esa ronda."""

    actions: np.ndarray          # (rondas, coches, 2): acción elegida por rol, tal cual (D/D queda como D y D)
    beliefs: np.ndarray          # (rondas + 1, coches, 2): creencia de que el rival sigue, incluye la inicial
    outcomes: list[Counter]      # resultado de los encuentros de cada ronda ("CC", "A", "B", "DD")


class CityModel(ap.Model):
    """La ciudad: red vial, coches persistentes y semáforos BDI.

    Parámetros: `n_cars`, `seed`, `network` (opcional, para no reconstruirla), `drivers` (ruta al JSON
    de `train.ipynb`; si no existe, los conductores son novatos), `detour` (ETOILE_DETOUR),
    `spawn_spacing` (SPAWN_SPACING) y `steps` (opcional, corridas sin ventana).
    """

    def setup(self) -> None:
        self.network: RoadNetwork = self.p.get("network") or RoadNetwork()
        self.detour: int | None = self.p.get("detour", ETOILE_DETOUR)
        self.time = 0.0
        self.trips = 0
        self.trip_times: dict[str, list[float]] = {"etoile": [], "ring": []}   # viajes por glorieta
        self.trip_waits: list[float] = []
        self.journeys: list[tuple[str, int, float]] = []    # (ruta, calles hasta el destino, s)
        self.missed_exits = 0                # pasadas por la Étoile que necesitaron otra vuelta
        self.encounters = 0
        self.outcomes = Counter()            # jugadas en la calle, por resultado
        self.setup_lights()
        self.setup_cars()
        self.trained = self.load_drivers(self.p.get("drivers"))
        self.build_index()

    def setup_lights(self) -> None:
        """Un agente por radio saliente, con su línea de alto sobre el anillo y sus cabezas visibles."""
        heads = intersection_heads()
        outs = self.network.spokes("out")
        self.lights = ap.AgentList(self, len(outs), TrafficLightAgent)
        self.light_of: dict[str, TrafficLightAgent] = {}
        ring_len = self.network.lanes["ring"].length
        for light, sid in zip(self.lights, outs):
            spoke = self.network.lanes[sid]
            light.spoke_id, light.avenue = sid, spoke.avenue
            light.ring_stop_s = (spoke.end_s - spoke.tail_len - LIGHT_STOP_BACK) % ring_len
            light.heads = heads.pop(spoke.avenue)
            light.sync_heads()
            self.light_of[sid] = light
        self._ring_stops = sorted(((l.ring_stop_s, l) for l in self.lights), key=lambda t: t[0])
        # Cruces sin radio saliente (Mac-Mahon): nadie se incorpora, el anillo siempre pasa
        for static in heads.values():
            for approach, head in static.items():
                head.set_state("green" if approach == "ring" else "red")
        self.light_heads: list[TrafficLight] = (
            [h for light in self.lights for h in light.heads.values()]
            + [h for static in heads.values() for h in static.values()])

    def setup_cars(self) -> None:
        """Lo único con posiciones concretas: coches repartidos sin traslapes en los 22 radios."""
        slots = [(lane_id, s) for lane_id, lane in self.network.lanes.items() if not lane.loop
                 for s in np.arange(SPAWN_MARGIN, lane.stop_s - SPAWN_MARGIN,
                                    self.p.get("spawn_spacing", SPAWN_SPACING))]
        n_cars = self.p.get("n_cars", N_CARS)
        if n_cars > len(slots):
            raise ValueError(f"caben a lo más {len(slots)} coches")
        self.cars = ap.AgentList(self, n_cars, CarAgent)
        for car, (lane_id, s) in zip(self.cars, self.random.sample(slots, n_cars)):
            car.v = START_SPEED
            car.enter_lane(lane_id, s)

    def load_drivers(self, path: str | None) -> bool:
        """Carga los conteos del curso de manejo. Sin archivo, los conductores quedan novatos."""
        if not path or not Path(path).exists():
            return False
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        counts = np.array(data["counts"], dtype=float)
        if len(counts) != len(self.cars):
            raise ValueError(f"{path} tiene {len(counts)} conductores y el modelo {len(self.cars)}: "
                             "vuelve a correr train.ipynb con el mismo número de coches")
        for car, c in zip(self.cars, counts):
            car.counts = c.copy()
        return True

    # --- juego de dos roles ---
    def warmup(self, rounds: int) -> SchoolLog:
        """Curso de manejo: rondas en parejas, sin gráficos. Baraja, forma parejas, sortea roles y juegan."""
        cars = list(self.cars)
        n = len(cars)
        actions = np.full((rounds, n, 2), np.nan)
        beliefs = np.full((rounds + 1, n, 2), np.nan)
        outcomes: list[Counter] = []
        beliefs[0] = [[belief(c.counts[role]) for role in (ROLE_A, ROLE_B)] for c in cars]
        for r in range(rounds):
            order = self.random.sample(range(n), n)            # define parejas y roles; si n es impar, uno descansa
            tally = Counter()
            for i, j in zip(order[::2], order[1::2]):
                a, b = self.encounter(cars[i], cars[j])
                actions[r, i, ROLE_A], actions[r, j, ROLE_B] = a, b
                tally[OUTCOMES[a, b]] += 1
            outcomes.append(tally)
            beliefs[r + 1] = [[belief(c.counts[role]) for role in (ROLE_A, ROLE_B)] for c in cars]
        return SchoolLog(actions, beliefs, outcomes)

    def encounter(self, car_a: CarAgent, car_b: CarAgent) -> tuple[int, int]:
        """Una jugada: eligen al mismo tiempo y se avisan con INFORM; cada uno aprende de lo que vio."""
        a, b = play(car_a.counts, car_b.counts, self.random)
        car_a.receive(Inform(car_b.id, "merge_action", {"role": ROLE_B, "action": b}))
        car_b.receive(Inform(car_a.id, "merge_action", {"role": ROLE_A, "action": a}))
        return a, b

    def start_encounter(self, entrant: CarAgent, rival: CarAgent) -> dict:
        """Nuevo encuentro en la calle. Si A ya no alcanza a frenar, pasa sin jugar."""
        lane = entrant.lane
        entrant.encounter = {"rival": rival, "winner": None, "retry_at": self.time}
        ring_len = self.network.lanes["etoile_0"].length
        room = (lane.end_s - rival.s) % ring_len - lane.tail_len - YIELD_BACK
        if room < rival.v ** 2 / (2 * YIELD_DECEL):
            entrant.encounter["winner"] = ROLE_A
        else:
            self.encounters += 1
            self.play_merge(entrant)
        return entrant.encounter

    def play_merge(self, entrant: CarAgent) -> None:
        """Juega (o vuelve a jugar) el encuentro de un entrante y aplica el resultado en la calle.

        D/C: pasa quien siguió. C/C: los dos frenan y vuelven a jugar tras RETRY_TIME. D/D: se registra
        como tal; los dos frenan de golpe (no hay física de choques) y vuelven a jugar.
        """
        e, lane = entrant.encounter, entrant.lane
        rival = e["rival"]
        a, b = self.encounter(rival, entrant)                  # A circula por la Étoile, B se integra
        self.outcomes[OUTCOMES[a, b]] += 1
        stop_s = lane.end_s - lane.tail_len - YIELD_BACK       # detrás de donde aparecerá el entrante
        rival.yield_line = None if (a, b) == (D, C) else (stop_s, entrant, self.time)
        if a != b:
            e["winner"] = ROLE_A if a == D else ROLE_B
            return
        e["retry_at"] = self.time + RETRY_TIME
        if a == D:
            entrant.v = rival.v = 0.0

    # --- utilidades ---
    def build_index(self) -> None:
        """Foto de cada carril, ordenada por s. Quien va por la curva final de un radio aparece
        también proyectado en el anillo al que se incorpora, para que los de la glorieta lo sigan."""
        self.index = {lid: LaneIndex(lane) for lid, lane in self.network.lanes.items()}
        for car in self.cars:
            self.index[car.lane_id].add(car.s, car)
            lane = car.lane
            if not lane.loop and car.crossed:
                end_len = self.network.lanes[lane.end_lane].length
                self.index[lane.end_lane].add(car.projected_s() % end_len, car)

    def next_ring_light(self, s: float) -> tuple[TrafficLightAgent | None, float]:
        ring_len = self.network.lanes["ring"].length
        best, best_d = None, math.inf
        for stop_s, light in self._ring_stops:
            d = (stop_s - s) % ring_len
            if d < best_d:
                best, best_d = light, d
        return best, best_d

    def finish_trip(self, car: CarAgent, ring: str) -> None:
        """Un viaje es ir de una calle a la siguiente por una glorieta (`ring` = "etoile" o "ring")."""
        self.trips += 1
        self.trip_times[ring].append(self.time - car.trip_start)
        self.trip_waits.append(car.trip_wait)
        if ring == "etoile" and car.laps > 0:
            self.missed_exits += 1

    def finish_journey(self, car: CarAgent) -> None:
        """Llegó a su calle destino, con o sin desvío por la Étoile."""
        self.journeys.append((car.route, car.journey_streets, self.time - car.journey_start))

    def min_gap(self) -> float:
        """Distancia mínima entre defensas de coches del mismo carril (debe ser ≥ 0)."""
        worst = math.inf
        for idx in self.index.values():
            cars = sorted(c.s for c in idx.cars if c.lane_id == idx.lane.id)
            for s1, s2 in zip(cars, cars[1:]):
                worst = min(worst, s2 - s1 - CAR_LENGTH)
            if idx.lane.loop and len(cars) > 1:
                worst = min(worst, cars[0] + idx.lane.length - cars[-1] - CAR_LENGTH)
        return worst

    # --- ciclo de AgentPy ---
    def step(self) -> None:
        self.lights.step()
        for head in self.light_heads:
            head.state_time += SIM_DT
        self.build_index()
        for car in self.cars:
            car.decide()
        for car in self.cars:
            car.move()
        self.time += SIM_DT

    def update(self) -> None:
        if self.t == 0:
            return
        self.build_index()
        etoile = [sum(1 for c in self.cars if c.lane_id == f"etoile_{k}") for k in range(ETOILE_LANES)]
        n_etoile = max(1, sum(etoile))
        self.record("time", self.time)
        self.record("trips", self.trips)
        self.record("etoile_trips", len(self.trip_times["etoile"]))
        self.record("encounters", self.encounters)
        for key in OUTCOMES.values():
            self.record(f"plays_{key}", self.outcomes[key])
        self.record("mean_speed", float(np.mean([c.v for c in self.cars])))
        for role, name in ((ROLE_A, "A"), (ROLE_B, "B")):
            self.record(f"belief_{name}", float(np.mean([belief(c.counts[role]) for c in self.cars])))
        self.record("min_gap", self.min_gap())
        self.record("max_merge_queue", max(l.queues["MERGE"] for l in self.lights))
        for state in STATES:
            self.record(f"n_{state}", sum(1 for c in self.cars if c.state == state))
        for k in range(ETOILE_LANES):
            self.record(f"lane_share_{k}", etoile[k] / n_etoile)

    def end(self) -> None:
        def mean(xs: list[float]) -> float:
            return float(np.mean(xs)) if xs else math.nan

        plays = max(1, sum(self.outcomes.values()))
        self.report("trips", self.trips)
        self.report("etoile_trip_time", mean(self.trip_times["etoile"]))
        self.report("ring_trip_time", mean(self.trip_times["ring"]))
        self.report("mean_trip_wait", mean(self.trip_waits))
        self.report("missed_exit_share", self.missed_exits / max(1, len(self.trip_times["etoile"])))
        self.report("encounters", self.encounters)
        for key in OUTCOMES.values():
            self.report(f"share_{key}", self.outcomes[key] / plays)


if __name__ == "__main__":
    # Corrida sin ventana (M2): sin traslapes y sin atasco total en 10 min simulados
    from config import DRIVERS_FILE

    minutes = 10
    model = CityModel({"n_cars": N_CARS, "seed": SEED, "drivers": DRIVERS_FILE,
                       "steps": int(minutes * 60 / SIM_DT)})
    results = model.run(display=False)
    df = results.variables.CityModel
    last_minute = int(60 / SIM_DT)
    print(f"conductores: {'con curso' if model.trained else 'novatos'}")
    print(results.reporters.T)
    print(f"distancia mínima entre defensas: {df['min_gap'].min():.2f} m")
    print(f"viajes en el último minuto: {int(df['trips'].iloc[-1] - df['trips'].iloc[-1 - last_minute])}")
    assert df["min_gap"].min() >= -1e-6, "hay traslapes"
    assert df["trips"].iloc[-1] > df["trips"].iloc[-1 - last_minute], "atasco total: nadie completa viajes"
    print("OK")
