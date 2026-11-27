#  Franco De Escondrillas ft. Claude Code · 2026-11-26
"""Funciones puras de teoría de juegos y el mensaje INFORM que comparten coches y semáforos.

- Étoile: juego de dos roles (A se integra, B circula) con juego ficticio.
- Anillo exterior: valor de Shapley para repartir el verde entre las fases de un semáforo.
"""

from __future__ import annotations

import itertools
import math
from dataclasses import dataclass
from typing import Callable, Hashable

import numpy as np

from config import CONVOY_D, CONVOY_H, CYCLE_TIME, PAYOFFS as _PAYOFFS

ROLE_A, ROLE_B = 0, 1        # A: el que se integra · B: el que circula por el carril 0
BRAKE, GO = 0, 1             # frenar (C) y seguir (D)
PAYOFFS = np.array(_PAYOFFS)  # PAYOFFS[rol][acción propia][acción del rival]
OUTCOMES = {(BRAKE, BRAKE): "CC", (GO, BRAKE): "A", (BRAKE, GO): "B", (GO, GO): "DD"}
OUTCOME_LABELS = {"CC": "los dos frenan (C/C)", "B": "pasa B, la glorieta",
                  "A": "pasa A, el que se integra", "DD": "los dos siguen (D/D)"}


@dataclass
class Inform:
    """Mensaje INFORM (FIPA): quién lo manda, de qué trata y el contenido."""

    sender: int
    topic: str          # "merge_action" (coche → coche) o "approach" (coche → semáforo)
    content: dict


# --- Étoile: juego ficticio ---
def belief(counts: np.ndarray) -> float:
    """Probabilidad que un coche le da a que su rival siga, según lo que ha visto (`counts` de un rol)."""
    return float(counts[GO] / counts.sum())


def best_response(payoff: np.ndarray, counts: np.ndarray, rng) -> int:
    """Acción de mayor pago esperado contra la frecuencia observada (empate al azar)."""
    expected = payoff @ (counts / counts.sum())
    return rng.choice([int(a) for a in np.flatnonzero(np.isclose(expected, expected.max()))])


def play(counts_a: np.ndarray, counts_b: np.ndarray, rng) -> tuple[int, int]:
    """Un encuentro: A y B eligen al mismo tiempo, cada uno con los conteos de su propio rol."""
    return (best_response(PAYOFFS[ROLE_A], counts_a[ROLE_A], rng),
            best_response(PAYOFFS[ROLE_B], counts_b[ROLE_B], rng))


def go_threshold(role: int) -> float:
    """Creencia por debajo de la cual conviene seguir: la p* que iguala los pagos de seguir y frenar."""
    (cc, cd), (dc, dd) = PAYOFFS[role]
    return float((dc - cc) / ((dc - cc) + (cd - dd)))


# --- Anillo exterior: coaliciones ---
def shapley(players: list[Hashable], v: Callable[[frozenset], float]) -> dict:
    """Valor de Shapley por fuerza bruta (n ≤ 4): `v` recibe un frozenset y devuelve su valor."""
    n = len(players)
    phi = {}
    for i in players:
        others = [j for j in players if j != i]
        total = 0.0
        for r in range(n):
            for subset in itertools.combinations(others, r):
                s = frozenset(subset)
                weight = math.factorial(len(s)) * math.factorial(n - len(s) - 1) / math.factorial(n)
                total += weight * (v(s | {i}) - v(s))
        phi[i] = total
    return phi


def coalition_value(queues: dict[str, int], coalition: frozenset) -> float:
    """Tiempo que ahorra servir las colas de la coalición en un solo convoy: N·ciclo − τ(N), τ(n) = d + n·h."""
    n = sum(queues[p] for p in coalition)
    return 0.0 if n == 0 else n * CYCLE_TIME - (CONVOY_D + n * CONVOY_H)


def green_split(queues: dict[str, int], default: str) -> tuple[dict, dict]:
    """(φ, fracción del ciclo) por fase; sin colas, todo el verde es para la fase `default`."""
    phi = shapley(list(queues), lambda s: coalition_value(queues, s))
    total = sum(phi.values())
    share = {p: phi[p] / total if total > 0 else float(p == default) for p in queues}
    return phi, share
