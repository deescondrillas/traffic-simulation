# A01739410 – Franco De Escondrillas
# A01739769 – Enrique Jiménez
# 2026-11-18

from sim.config import BLINK_TIME, MERGE_GREEN_TIME, RING_GREEN_TIME, YELLOW_TIME
from dataclasses import dataclass


@dataclass
class TrafficLight:
  """Un semáforo en una aproximación al anillo exterior.

  `approach` es "ring" (el anillo antes del cruce), "merge" (el radio que sale de la
  Étoile y se incorpora) u "outside" (la avenida que llega desde fuera del mapa).
  """

  avenue: str
  approach: str
  x: float
  z: float
  yaw: float # rad, giro del modelo alrededor de Y para que los focos miren al tráfico
  state: str = "red"
  state_time: float = 0.0 # s en el estado actual, para el parpadeo

  def set_state(self, state: str) -> None:
    if state != self.state:
      self.state = state
      self.state_time = 0.0


class FixedTimeIntersection:
  """Ciclo fijo de un cruce: verde al anillo y luego al radio que se incorpora.

  Es provisional: `TrafficLightAgent` (BDI + Shapley) lo reemplaza en M4. La avenida
  que llega desde fuera copia al radio que se incorpora, aunque no traiga coches; sin
  radio (Av. Mac-Mahon) el anillo queda siempre en verde y la de fuera en rojo.
  """

  def __init__(self, ring: TrafficLight, merge: TrafficLight | None, outside: TrafficLight | None) -> None:
    self.ring = ring
    self.merge = merge
    self.outside = outside
    self._phases = []
    for light, green_time in ((ring, RING_GREEN_TIME), (merge, MERGE_GREEN_TIME)):
      self._phases += [(light, "green", green_time), (light, "blinking_green", BLINK_TIME), (light, "yellow", YELLOW_TIME)]
    self._phase = 0
    self._phase_time = 0.0
    self._apply()

  def step(self, dt: float) -> None:
    for light in self.lights:
      light.state_time += dt
    if self.merge is None:
      return
    self._phase_time += dt
    if self._phase_time >= self._phases[self._phase][2]:
      self._phase_time -= self._phases[self._phase][2]
      self._phase = (self._phase + 1) % len(self._phases)
      self._apply()

  @property
  def lights(self) -> list[TrafficLight]:
    return [light for light in (self.ring, self.merge, self.outside) if light is not None]

  def _apply(self) -> None:
    if self.merge is None:
      self.ring.set_state("green")
      if self.outside is not None:
        self.outside.set_state("red")
      return
    active, state, _ = self._phases[self._phase]
    for light in (self.ring, self.merge):
      light.set_state(state if light is active else "red")
    if self.outside is not None:
      self.outside.set_state(self.merge.state)
