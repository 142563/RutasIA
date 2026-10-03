"""Cliente de Google Routes API (computeRouteMatrix).

Solo lo usan los comandos por lotes (build_graph, calibrate_traffic). El motor
de rutas NUNCA llama a Google: trabaja con el grafo en memoria.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone as dt_timezone
from typing import Sequence

import httpx
from django.conf import settings

MATRIX_URL = "https://routes.googleapis.com/distanceMatrix/v2:computeRouteMatrix"
FIELD_MASK = "originIndex,destinationIndex,status,condition,distanceMeters,duration,staticDuration"

ROUTES_URL = "https://routes.googleapis.com/directions/v2:computeRoutes"
ROUTE_FIELD_MASK = "routes.duration,routes.staticDuration,routes.distanceMeters"

TRAFFIC_UNAWARE = "TRAFFIC_UNAWARE"
TRAFFIC_AWARE_OPTIMAL = "TRAFFIC_AWARE_OPTIMAL"

LatLng = tuple[float, float]


class RoutesApiError(Exception):
    pass


@dataclass(frozen=True)
class MatrixElement:
    origin_index: int
    destination_index: int
    status: str  # "" = OK; si no, el error o la condición que devolvió Google
    distance_m: float | None
    duration_s: float | None
    static_duration_s: float | None

    @property
    def ok(self) -> bool:
        return not self.status and self.distance_m is not None and self.duration_s is not None


def parse_duration(value: str | None) -> float | None:
    """Google devuelve duraciones como "123s" (formato protobuf Duration)."""
    if not value:
        return None
    if not value.endswith("s"):
        raise RoutesApiError(f"Duración con formato inesperado: {value!r}")
    return float(value[:-1])


def to_rfc3339(moment: datetime) -> str:
    return moment.astimezone(dt_timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


@dataclass(frozen=True)
class RouteResult:
    duration_s: float  # con el tráfico del momento
    static_duration_s: float | None  # sin tráfico
    distance_m: float


def _via_waypoint(point: LatLng) -> dict:
    lat, lng = point
    # via: true = "pasa por aquí" sin detenerse; así Google mide exactamente nuestra ruta.
    return {"via": True, "location": {"latLng": {"latitude": lat, "longitude": lng}}}


def _waypoint(point: LatLng) -> dict:
    lat, lng = point
    return {"waypoint": {"location": {"latLng": {"latitude": lat, "longitude": lng}}}}


def parse_matrix_response(payload: list[dict]) -> list[MatrixElement]:
    elements = []
    for raw in payload:
        # proto3 en JSON omite los enteros en 0: originIndex ausente significa 0.
        status = raw.get("status") or {}
        error = status.get("message") or (f"code {status['code']}" if status.get("code") else "")
        condition = raw.get("condition", "")
        if not error and condition and condition != "ROUTE_EXISTS":
            error = condition
        distance = raw.get("distanceMeters")
        elements.append(MatrixElement(
            origin_index=raw.get("originIndex", 0),
            destination_index=raw.get("destinationIndex", 0),
            status=error,
            distance_m=float(distance) if distance is not None and not error else None,
            duration_s=parse_duration(raw.get("duration")) if not error else None,
            static_duration_s=parse_duration(raw.get("staticDuration")) if not error else None,
        ))
    return elements


class RoutesClient:
    def __init__(self, api_key: str | None = None, http: httpx.Client | None = None, timeout: float = 30.0):
        self.api_key = api_key if api_key is not None else settings.GOOGLE_ROUTES_API_KEY
        if not self.api_key:
            raise RoutesApiError(
                "Falta GOOGLE_ROUTES_API_KEY en .env. Usa el modo sin conexión "
                "(--estimate / --synthetic) o agrega la key del servidor."
            )
        self.http = http or httpx.Client(timeout=timeout)
        self.requests_made = 0
        self.elements_requested = 0

    def compute_route_matrix(
        self,
        origins: Sequence[LatLng],
        destinations: Sequence[LatLng],
        departure_time: datetime | None = None,
        traffic: bool = False,
    ) -> list[MatrixElement]:
        body: dict = {
            "origins": [_waypoint(p) for p in origins],
            "destinations": [_waypoint(p) for p in destinations],
            "travelMode": "DRIVE",
            "routingPreference": TRAFFIC_AWARE_OPTIMAL if traffic else TRAFFIC_UNAWARE,
        }
        if departure_time is not None:
            body["departureTime"] = to_rfc3339(departure_time)

        response = self.http.post(
            MATRIX_URL,
            json=body,
            headers={"X-Goog-Api-Key": self.api_key, "X-Goog-FieldMask": FIELD_MASK},
        )
        self.requests_made += 1
        self.elements_requested += len(origins) * len(destinations)
        if response.status_code != 200:
            raise RoutesApiError(f"Routes API respondió {response.status_code}: {response.text[:300]}")
        return parse_matrix_response(response.json())

    def compute_route(
        self,
        origin: LatLng,
        destination: LatLng,
        intermediates: Sequence[LatLng] = (),
        departure_time: datetime | None = None,
    ) -> RouteResult:
        """Una consulta computeRoutes con tráfico, pasando por los nodos intermedios dados."""
        body: dict = {
            "origin": {"location": {"latLng": {"latitude": origin[0], "longitude": origin[1]}}},
            "destination": {"location": {"latLng": {"latitude": destination[0], "longitude": destination[1]}}},
            "travelMode": "DRIVE",
            "routingPreference": TRAFFIC_AWARE_OPTIMAL,
        }
        if intermediates:
            body["intermediates"] = [_via_waypoint(p) for p in intermediates]
        if departure_time is not None:
            body["departureTime"] = to_rfc3339(departure_time)
        response = self.http.post(
            ROUTES_URL, json=body,
            headers={"X-Goog-Api-Key": self.api_key, "X-Goog-FieldMask": ROUTE_FIELD_MASK},
        )
        self.requests_made += 1
        if response.status_code != 200:
            raise RoutesApiError(f"Routes API respondió {response.status_code}: {response.text[:300]}")
        routes = response.json().get("routes") or []
        if not routes:
            raise RoutesApiError("Google no devolvió una ruta para este tramo.")
        raw = routes[0]
        duration = parse_duration(raw.get("duration"))
        if duration is None:
            raise RoutesApiError("Google no devolvió la duración del tramo.")
        return RouteResult(
            duration_s=duration,
            static_duration_s=parse_duration(raw.get("staticDuration")),
            distance_m=float(raw.get("distanceMeters", 0)),
        )
