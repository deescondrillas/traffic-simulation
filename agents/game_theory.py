# A01739410 – Franco De Escondrillas
# A01739769 – Enrique Jiménez
# 2026-11-30

from math import factorial, isclose
from dataclasses import dataclass
from config import CYCLE_TIME
import itertools


# A: coche en rotonda, B: coche integrándose
C, D = 0, 1
ROLE_A, ROLE_B = 0, 1

PAYOFFS = (
    #  B frena (C)    B sigue (D)
    ((-3.0, -2.0), ( -2.0,   0.0)),    # A frena (C)
    (( 0.0, -1.0), (-20.0, -20.0)),    # A sigue (D)
)
OUTCOMES = {(C, C): "CC", (D, C): "A", (C, D): "B", (D, D): "DD"}

CONVOY_D = 2.0               # s de arranque de un convoy, τ(n) = d + n·h
CONVOY_H = 2.0               # s entre coches de un convoy


@dataclass
class Inform:
    """Mensaje INFORM (FIPA): quién lo manda, de qué trata y el contenido."""

    sender: int
    topic: str          # "merge_action" (coche → coche) o "approach" (coche → semáforo)
    content: dict


# --- Étoile: juego ficticio ---
def belief(counts) -> float:
    """Creencia de que el rival defecte (no frenar)."""
    return float(counts[D] / (counts[C] + counts[D]))


def payoff(role: int, own: int, rival: int) -> float:
    """Pago de `role` (0 = A, 1 = B) cuando juega `own` y su rival `rival`."""
    a, b = (own, rival) if role == 0 else (rival, own)
    return PAYOFFS[a][b][role]


def best_response(role: int, counts, rng) -> int:
    """Acción de mayor pago con base en creencias (al azar si empatan)."""
    p_go = belief(counts)
    expected = [payoff(role, a, C) * (1 - p_go) + payoff(role, a, D) * p_go for a in (C, D)]
    best = max(expected)
    return rng.choice([a for a in (C, D) if isclose(expected[a], best)])


def play(counts_a, counts_b, rng) -> tuple[int, int]:
    """Un encuentro: A y B eligen al mismo tiempo, cada uno con los conteos de su propio rol."""
    return (best_response(ROLE_A, counts_a[ROLE_A], rng),
            best_response(ROLE_B, counts_b[ROLE_B], rng))


def go_threshold(role: int) -> float:
    """Creencia por debajo de la cual conviene seguir: la p* que iguala los pagos de seguir y frenar."""
    cc, cd = payoff(role, C, C), payoff(role, C, D)
    dc, dd = payoff(role, D, C), payoff(role, D, D)
    return (dc - cc) / ((dc - cc) + (cd - dd))


# --- Anillo exterior: coaliciones ---
def shapley(players: list, value) -> dict:
    """Valor de Shapley por fuerza bruta (n ≤ 4): `value(coalición)` recibe un frozenset y devuelve un número."""
    n = len(players)
    phi = {}
    for i in players:
        others = [j for j in players if j != i]
        total = 0.0
        for r in range(n):
            for subset in itertools.combinations(others, r):
                s = frozenset(subset)
                weight = factorial(len(s)) * factorial(n - len(s) - 1) / factorial(n)
                total += weight * (value(s | {i}) - value(s))
        phi[i] = total
    return phi


def coalition_value(queues: dict, coalition) -> float:
    """Tiempo que ahorra servir las colas de la coalición en un solo convoy: N·ciclo − τ(N), τ(n) = d + n·h."""
    n = sum(queues[p] for p in coalition)
    return 0.0 if n == 0 else n * CYCLE_TIME - (CONVOY_D + n * CONVOY_H)


def green_split(queues: dict, default: str) -> dict:
    """Fracción del ciclo para cada fase, proporcional a φ; sin colas, todo el verde es para `default`."""
    phi = shapley(list(queues), lambda s: coalition_value(queues, s))
    total = sum(phi.values())
    share = {}
    for p in queues:
        if total > 0:
            share[p] = phi[p] / total
        else:
            share[p] = 1.0 if p == default else 0.0
    return share
