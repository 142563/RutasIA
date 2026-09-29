"""Instrumentación de las búsquedas: toda búsqueda devuelve cuánto trabajó."""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Sequence

if TYPE_CHECKING:
    from logistics.routing.graph import RoadGraph

INF = math.inf


def reconstruct(graph: "RoadGraph", prev_edge: Sequence[int], source: int, target: int) -> tuple[list[int], list[int]]:
    """Camino (nodos) y aristas usadas, siguiendo prev_edge desde el destino."""
    nodes, edges = [target], []
    current = target
    while current != source:
        e = prev_edge[current]
        if e < 0:
            return [], []
        edges.append(e)
        current = graph.edge_from[e]
        nodes.append(current)
    nodes.reverse()
    edges.reverse()
    return nodes, edges


@dataclass
class SearchResult:
    """Resultado de una búsqueda punto a punto."""

    algorithm: str
    source: int
    target: int
    cost: float  # en la unidad de los pesos: minutos o km
    path: list[int]  # índices de nodos
    edges: list[int]  # índices de aristas
    expanded: int  # nodos cerrados (métrica principal, §2.9)
    pushed: int  # inserciones en el heap
    elapsed_ms: float
    order: list[int] | None = None  # orden de expansión (para el Laboratorio)
    v_max: float | None = None  # solo A*

    @property
    def found(self) -> bool:
        return self.cost < INF

    def total(self, values: Sequence[float]) -> float:
        """Suma de una magnitud por arista a lo largo de la ruta (p. ej. km o minutos)."""
        return sum(values[e] for e in self.edges)

    def path_codes(self, graph: "RoadGraph") -> list[str]:
        return [graph.codes[i] for i in self.path]


@dataclass
class ShortestPathTree:
    """Resultado de Dijkstra uno-a-todos."""

    source: int
    dist: list[float]
    prev_edge: list[int]
    expanded: int
    pushed: int
    elapsed_ms: float
    order: list[int] | None = field(default=None)

    def path_to(self, graph: "RoadGraph", target: int) -> tuple[list[int], list[int]]:
        if self.dist[target] == INF:
            return [], []
        return reconstruct(graph, self.prev_edge, self.source, target)
