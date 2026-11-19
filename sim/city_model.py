# A01739410 – Franco De Escondrillas
# A01739769 – Enrique Jiménez
# 2026-11-18

from sim.traffic_light import FixedTimeIntersection, TrafficLight
from sim.config import SIM_DT, TRAFFIC_LIGHTS
from math import pi, radians
import agentpy as ap

Intersection = tuple[TrafficLight, TrafficLight | None, TrafficLight | None]  # anillo, radio, afuera


def intersection_lights() -> dict[str, Intersection]:
    """Semáforos de `TRAFFIC_LIGHTS` agrupados por cruce, en el orden de la tabla."""
    approaches = {}
    for avenue, approach, x, z, heading in TRAFFIC_LIGHTS:
        light = TrafficLight(avenue, approach, x, z, radians(heading) - pi / 2)
        approaches.setdefault(avenue, {})[approach] = light
    return {
        avenue: (lights["ring"], lights.get("merge"), lights.get("outside"))
        for avenue, lights in approaches.items()
    }


class CityModel(ap.Model):
    """La ciudad: por ahora solo los semáforos del anillo exterior con ciclo fijo."""
    def setup(self) -> None:
        self.intersections = [FixedTimeIntersection(*lights) for lights in intersection_lights().values()]
        self.lights = [light for intersection in self.intersections for light in intersection.lights]

    def step(self) -> None:
        for intersection in self.intersections:
            intersection.step(SIM_DT)
