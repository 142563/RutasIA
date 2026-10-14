"""Algoritmo genético para el orden de visita (tesis, Cap. III: motor principal).

Individuo = una secuencia completa de entrega (permutación de las paradas 1..k;
la bodega es el índice 0 de la matriz). Aptitud = tiempo total estimado del
recorrido, menor es mejor. Por defecto se mide con la matriz; el planificador pasa
`fitness` dependiente del tiempo (cada tramo con el tráfico de la franja en que
empieza, multistop.TimeDependentCost), y entonces la matriz solo guía al 2-opt.

Operadores:
- Selección por torneo.
- Cruce de orden (OX), que siempre produce permutaciones válidas.
- Mutación por intercambio o por inversión de un tramo.
- Elitismo: los mejores pasan intactos a la siguiente generación.
- Búsqueda local 2-opt sobre los élites (variante memética), con el costo de
  invertir un tramo calculado en O(1) por sumas acumuladas; la matriz NO es
  simétrica, así que se usan dos sumas: hacia adelante y en reversa.

La población inicial incluye el vecino más cercano, así que el resultado nunca
es peor que esa heurística. Semilla fija = resultados reproducibles.
Solo biblioteca estándar; los parámetros los ajusta el administrador
(OptimizerSettings) y por defecto valen GeneticParams().
"""
from __future__ import annotations

import random
import time
from dataclasses import dataclass, field, fields
from typing import Callable, Sequence

EPS = 1e-9


@dataclass(frozen=True)
class GeneticParams:
    population: int = 80
    generations: int = 400
    tournament: int = 3
    crossover_rate: float = 0.9
    mutation_rate: float = 0.2
    elitism: int = 2
    stall_generations: int = 60  # se detiene si el mejor no mejora en tantas generaciones
    seed: int | None = 2026
    local_search: bool = True
    local_search_rate: float = 0.1  # fracción de hijos que se pulen con 2-opt

    def clamped(self) -> "GeneticParams":
        """Valores dentro de rangos sensatos (lo que venga de la configuración)."""
        return GeneticParams(
            population=max(4, min(int(self.population), 1000)),
            generations=max(1, min(int(self.generations), 5000)),
            tournament=max(2, min(int(self.tournament), 10)),
            crossover_rate=max(0.0, min(float(self.crossover_rate), 1.0)),
            mutation_rate=max(0.0, min(float(self.mutation_rate), 1.0)),
            elitism=max(0, min(int(self.elitism), 20)),
            stall_generations=max(1, min(int(self.stall_generations), 5000)),
            seed=self.seed,
            local_search=bool(self.local_search),
            local_search_rate=max(0.0, min(float(self.local_search_rate), 1.0)),
        )

    @classmethod
    def names(cls) -> list[str]:
        return [f.name for f in fields(cls)]


@dataclass
class GeneticResult:
    order: list[int]  # índices 1..k de la matriz, en orden de visita
    cost: float
    generations: int
    stop_reason: str  # "generations" | "stall" | "trivial"
    history: list[float] = field(default_factory=list)  # mejor costo por generación
    ms: float = 0.0


def tour_cost(order: Sequence[int], matrix: Sequence[Sequence[float]], return_to_depot: bool) -> float:
    total, current = 0.0, 0
    for stop in order:
        total += matrix[current][stop]
        current = stop
    if return_to_depot:
        total += matrix[current][0]
    return total


def nearest_neighbor_order(matrix: Sequence[Sequence[float]]) -> list[int]:
    pending = set(range(1, len(matrix)))
    order, current = [], 0
    while pending:
        nxt = min(pending, key=lambda j: (matrix[current][j], j))
        order.append(nxt)
        pending.remove(nxt)
        current = nxt
    return order


def ordered_crossover(a: Sequence[int], b: Sequence[int], rng: random.Random) -> list[int]:
    """OX: copia un tramo de `a` y completa con el orden de `b`."""
    n = len(a)
    i, j = sorted(rng.sample(range(n), 2)) if n > 1 else (0, 0)
    child: list[int | None] = [None] * n
    child[i:j + 1] = a[i:j + 1]
    taken = set(a[i:j + 1])
    fill = (g for g in b if g not in taken)
    for k in range(n):
        if child[k] is None:
            child[k] = next(fill)
    return child  # type: ignore[return-value]


def mutate(order: list[int], rng: random.Random) -> None:
    n = len(order)
    if n < 2:
        return
    i, j = sorted(rng.sample(range(n), 2))
    if rng.random() < 0.5:
        order[i], order[j] = order[j], order[i]
    else:
        order[i:j + 1] = reversed(order[i:j + 1])


def fast_two_opt(order: Sequence[int], matrix: Sequence[Sequence[float]], return_to_depot: bool,
                 max_passes: int = 50) -> list[int]:
    """2-opt para matriz asimétrica con costo de cada inversión en O(1).

    seq = [0, *order, (0)]. Invertir seq[i..j] cambia los arcos de entrada y
    salida del tramo y el sentido de los arcos internos: forward(i..j) pasa a
    backward(i..j), que salen de dos sumas acumuladas.
    """
    best = list(order)
    n = len(best)
    if n < 2:
        return best
    for _ in range(max_passes):
        seq = [0, *best] + ([0] if return_to_depot else [])
        m = len(seq)
        fwd = [0.0] * m  # fwd[k] = suma de seq[t]->seq[t+1] para t < k
        bwd = [0.0] * m  # bwd[k] = suma de seq[t+1]->seq[t] para t < k
        for t in range(m - 1):
            fwd[t + 1] = fwd[t] + matrix[seq[t]][seq[t + 1]]
            bwd[t + 1] = bwd[t] + matrix[seq[t + 1]][seq[t]]
        improved = False
        # Posiciones invertibles: 1..n (las paradas); seq[0] y el regreso quedan fijos
        for i in range(1, n):
            a = seq[i - 1]
            for j in range(i + 1, n + 1):
                b, c = seq[i], seq[j]
                old = matrix[a][b] + (fwd[j] - fwd[i])
                new = matrix[a][c] + (bwd[j] - bwd[i])
                if j + 1 < m:
                    d = seq[j + 1]
                    old += matrix[c][d]
                    new += matrix[b][d]
                if new < old - EPS:
                    best = best[:i - 1] + best[i - 1:j][::-1] + best[j:]
                    improved = True
                    break
            if improved:
                break
        if not improved:
            break
    return best


def solve(matrix: Sequence[Sequence[float]], params: GeneticParams | None = None,
          return_to_depot: bool = False, seeds: Sequence[Sequence[int]] = (),
          fitness: Callable[[Sequence[int]], float] | None = None) -> GeneticResult:
    """Mejor orden de visita encontrado por el genético para la matriz dada.

    `seeds` = órdenes conocidos que entran a la población inicial (p. ej. el de
    vecino más cercano + 2-opt); el resultado nunca es peor que ninguno de ellos.
    `fitness(order)` reemplaza al costo de la matriz (p. ej. tiempo dependiente de la franja).
    """
    started = time.perf_counter()
    params = (params or GeneticParams()).clamped()
    stops = list(range(1, len(matrix)))
    cost = fitness or (lambda o: tour_cost(o, matrix, return_to_depot))

    def polish(order: list[int]) -> list[int]:
        """2-opt guiado por la matriz; con otra aptitud solo se acepta si no empeora."""
        out = fast_two_opt(order, matrix, return_to_depot)
        return out if fitness is None or cost(out) <= cost(order) + EPS else order

    if len(stops) <= 2:
        # 0, 1 o 2 paradas: se prueban todas las opciones directamente
        options = [stops, stops[::-1]] if len(stops) == 2 else [stops]
        order = min(options, key=cost)
        return GeneticResult(order, cost(order), 0, "trivial", [cost(order)],
                             (time.perf_counter() - started) * 1000)

    rng = random.Random(params.seed)
    population = [list(s) for s in seeds if sorted(s) == stops]
    population.append(nearest_neighbor_order(matrix))
    if params.local_search:
        population.append(polish(population[-1]))
    polished_quota = len(population) + int(params.population * 0.2) if params.local_search else 0
    while len(population) < params.population:
        individual = stops[:]
        rng.shuffle(individual)
        if len(population) < polished_quota:
            # Parte de la población arranca en óptimos locales distintos (diversidad + calidad)
            individual = polish(individual)
        population.append(individual)
    population = population[:max(params.population, len(seeds) + 1)]
    scored = sorted(((cost(o), o) for o in population), key=lambda s: s[0])
    best_cost, best = scored[0]
    history, stall, generation, reason = [best_cost], 0, 0, "generations"
    elite_count = min(params.elitism, len(scored))

    def pick() -> list[int]:
        contenders = rng.sample(scored, min(params.tournament, len(scored)))
        return min(contenders, key=lambda s: s[0])[1]

    for generation in range(1, params.generations + 1):
        nxt = [list(o) for _, o in scored[:elite_count]]
        if params.local_search and generation % 10 == 0:
            nxt = [polish(o) for o in nxt]
        while len(nxt) < params.population:
            p1, p2 = pick(), pick()
            child = ordered_crossover(p1, p2, rng) if rng.random() < params.crossover_rate else list(p1)
            if rng.random() < params.mutation_rate:
                mutate(child, rng)
            if params.local_search and rng.random() < params.local_search_rate:
                child = polish(child)
            nxt.append(child)
        scored = sorted(((cost(o), o) for o in nxt), key=lambda s: s[0])
        if scored[0][0] < best_cost - EPS:
            best_cost, best, stall = scored[0][0], list(scored[0][1]), 0
        else:
            stall += 1
        history.append(best_cost)
        if stall >= params.stall_generations:
            reason = "stall"
            break

    if params.local_search:
        polished = polish(best)
        if cost(polished) < best_cost - EPS:
            best, best_cost = polished, cost(polished)
            history[-1] = best_cost
    return GeneticResult(best, best_cost, generation, reason, history, (time.perf_counter() - started) * 1000)
