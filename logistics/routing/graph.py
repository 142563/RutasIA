"""Grafo vial nacional en memoria (listas de adyacencia).

Se lee de la BD UNA vez y se guarda en el proceso: Dijkstra y A* nunca consultan
la BD ni Google dentro de su bucle. Los nodos se indexan 0..n-1 y las aristas
0..m-1; los pesos son listas alineadas con las aristas.
"""
from __future__ import annotations

import threading
from dataclasses import dataclass, field
from typing import Iterable, Sequence

from logistics.routing.geo import haversine_km

TIME = "time"
DISTANCE = "distance"
CRITERIA = (TIME, DISTANCE)

UNPAVED = "unpaved"
# Al evitar terracería, su costo de BÚSQUEDA se multiplica por este factor (≥ 1):
# solo se usa si la alternativa asfaltada tarda más de 20 veces. Los minutos que
# se muestran siguen siendo los reales (los de `weights`), nunca los penalizados.
UNPAVED_PENALTY = 20.0

Profile = tuple[str, str]  # (franja, tipo de día)


@dataclass
class RoadGraph:
    codes: list[str]
    names: list[str]
    lat: list[float]
    lon: list[float]
    edge_from: list[int]
    edge_to: list[int]
    t0: list[float]  # minutos sin tráfico
    km: list[float]
    roads: list[str] = field(default_factory=list)
    edge_db_ids: list[int | None] = field(default_factory=list)
    multipliers: dict[Profile, list[float]] = field(default_factory=dict)
    sources: dict[str, str] = field(default_factory=dict)  # de dónde salen los datos
    kinds: list[str] = field(default_factory=list)  # cabecera | municipio | cruce (para el mapa)
    road_classes: list[str] = field(default_factory=list)  # primary | secondary | unpaved, por arista

    def __post_init__(self) -> None:
        self.index = {code: i for i, code in enumerate(self.codes)}
        self.adj: list[list[tuple[int, int]]] = [[] for _ in self.codes]
        for e, (u, v) in enumerate(zip(self.edge_from, self.edge_to)):
            self.adj[u].append((v, e))
        if not self.roads:
            self.roads = [""] * len(self.t0)
        if not self.edge_db_ids:
            self.edge_db_ids = [None] * len(self.t0)
        if not self.kinds:
            self.kinds = [""] * len(self.codes)
        if not self.road_classes:
            self.road_classes = [""] * len(self.t0)
        self._weights_cache: dict[tuple, list[float]] = {}

    # --- construcción -----------------------------------------------------

    @classmethod
    def from_lists(
        cls,
        nodes: Iterable[tuple[str, str, float, float]],
        edges: Iterable[tuple[str, str, float, float]],
        multipliers: dict[Profile, Sequence[float]] | None = None,
        sources: dict[str, str] | None = None,
        road_classes: Sequence[str] | None = None,
    ) -> "RoadGraph":
        """Grafo sin BD. nodes = (code, name, lat, lon); edges = (origen, destino, km, t0_min)."""
        nodes = list(nodes)
        index = {code: i for i, (code, *_rest) in enumerate(nodes)}
        edges = list(edges)
        return cls(
            codes=[n[0] for n in nodes],
            names=[n[1] for n in nodes],
            lat=[n[2] for n in nodes],
            lon=[n[3] for n in nodes],
            edge_from=[index[e[0]] for e in edges],
            edge_to=[index[e[1]] for e in edges],
            km=[float(e[2]) for e in edges],
            t0=[float(e[3]) for e in edges],
            multipliers={k: list(v) for k, v in (multipliers or {}).items()},
            sources=sources or {},
            road_classes=list(road_classes or []),
        )

    # --- consultas --------------------------------------------------------

    @property
    def node_count(self) -> int:
        return len(self.codes)

    @property
    def edge_count(self) -> int:
        return len(self.t0)

    def weights(self, criterion: str = TIME, band: str | None = None, day_type: str | None = None) -> list[float]:
        """Peso de cada arista: minutos con tráfico (t0 × m) o km.

        Sin franja, o si esa franja no está calibrada, se usa m = 1 (t0).
        """
        if criterion not in CRITERIA:
            raise ValueError(f"Criterio inválido: {criterion}")
        key = (criterion, band, day_type)
        cached = self._weights_cache.get(key)
        if cached is not None:
            return cached
        if criterion == DISTANCE:
            result = self.km
        else:
            m = self.multipliers.get((band, day_type)) if band and day_type else None
            result = self.t0 if m is None else [t * factor for t, factor in zip(self.t0, m)]
        self._weights_cache[key] = result
        return result

    def search_weights(
        self, criterion: str = TIME, band: str | None = None, day_type: str | None = None,
        avoid_unpaved: bool = False,
    ) -> list[float]:
        """Pesos para BUSCAR la ruta. Con avoid_unpaved, la terracería cuesta ×UNPAVED_PENALTY.

        Solo multiplica por un factor ≥ 1: los pesos siguen ≥ 0 y A* (que deriva
        v_max de estos mismos pesos) sigue siendo exacto. Para mostrar minutos o
        km se usa siempre `weights`, no esta lista.
        """
        base = self.weights(criterion, band, day_type)
        if not avoid_unpaved or UNPAVED not in self.road_classes:
            return base
        key = ("avoid_unpaved", criterion, band, day_type)
        cached = self._weights_cache.get(key)
        if cached is None:
            cached = [w * UNPAVED_PENALTY if c == UNPAVED else w for w, c in zip(base, self.road_classes)]
            self._weights_cache[key] = cached
        return cached

    def unpaved_km(self, edges: Iterable[int]) -> float:
        return sum(self.km[e] for e in edges if self.road_classes[e] == UNPAVED)

    def straight_km(self, u: int, v: int) -> float:
        return haversine_km(self.lat[u], self.lon[u], self.lat[v], self.lon[v])

    def nearest_node(self, lat: float, lon: float) -> int:
        """Nodo más cercano en línea recta (fuerza bruta: el grafo tiene ~100 nodos)."""
        return min(range(self.node_count), key=lambda i: haversine_km(lat, lon, self.lat[i], self.lon[i]))

    def node_index(self, code: str) -> int:
        try:
            return self.index[code]
        except KeyError:
            raise KeyError(f"No existe el nodo '{code}' en el grafo.") from None


# --- carga desde la BD, cacheada en el proceso ------------------------------

_lock = threading.Lock()
_cached_graph: RoadGraph | None = None


def build_graph_from_db() -> RoadGraph:
    from logistics.models import Edge, Node, TrafficProfile

    nodes = list(Node.objects.filter(is_active=True).order_by("code"))
    index = {n.id: i for i, n in enumerate(nodes)}
    edges = [
        e for e in Edge.objects.filter(is_active=True).order_by("id")
        if e.origin_id in index and e.destination_id in index
    ]
    edge_pos = {e.id: i for i, e in enumerate(edges)}

    multipliers: dict[Profile, list[float]] = {}
    traffic_sources = set()
    for p in TrafficProfile.objects.filter(edge_id__in=edge_pos).only("edge_id", "band", "day_type", "multiplier", "source"):
        row = multipliers.setdefault((p.band, p.day_type), [1.0] * len(edges))
        row[edge_pos[p.edge_id]] = p.multiplier
        traffic_sources.add(p.source)

    return RoadGraph(
        codes=[n.code for n in nodes],
        names=[n.name for n in nodes],
        kinds=[n.kind for n in nodes],
        lat=[n.latitude for n in nodes],
        lon=[n.longitude for n in nodes],
        edge_from=[index[e.origin_id] for e in edges],
        edge_to=[index[e.destination_id] for e in edges],
        t0=[e.duration_free_min for e in edges],
        km=[e.distance_km for e in edges],
        roads=[e.road for e in edges],
        road_classes=[e.road_class for e in edges],
        edge_db_ids=[e.id for e in edges],
        multipliers=multipliers,
        sources={
            "edges": ",".join(sorted({e.source for e in edges})) or "none",
            "traffic": ",".join(sorted(traffic_sources)) or "none",
        },
    )


def load_graph() -> RoadGraph:
    """Grafo en memoria; se construye la primera vez y se reutiliza."""
    global _cached_graph
    with _lock:
        if _cached_graph is None:
            _cached_graph = build_graph_from_db()
        return _cached_graph


def invalidate_graph() -> None:
    """Llamar cuando cambian nodos, aristas o perfiles de tráfico (se hace con señales)."""
    global _cached_graph
    with _lock:
        _cached_graph = None
