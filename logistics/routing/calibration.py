"""Calibración de los 14 perfiles de tráfico (7 franjas × laboral/fin de semana).

Con Google: para cada perfil se pide la matriz con TRAFFIC_AWARE_OPTIMAL y una
salida futura representativa. Luego, por arista:

    t0 = min(staticDuration, duración mínima observada en los 14 perfiles)
    m  = duración del perfil / t0            →  m ≥ 1 por construcción

Así nunca se recorta ni se inventa un dato: si Google estima que de madrugada se
va más rápido que su staticDuration, ese tiempo pasa a ser el t0.

Sin conexión (--synthetic): multiplicadores de un modelo simple, marcados con
source="synthetic". Sirven para desarrollar; NO son datos de tesis.
"""
from __future__ import annotations

import random
from dataclasses import dataclass, field
from datetime import datetime

from django.db import transaction
from django.utils import timezone

from logistics.models import DayType, Edge, Node, TrafficBand, TrafficProfile
from logistics.routing.build import fetch_samples
from logistics.routing.geo import haversine_km
from logistics.routing.google import RoutesClient
from logistics.routing.graph import invalidate_graph
from logistics.routing.traffic import representative_departure

PROFILES = [(band, day) for day in DayType.values for band in TrafficBand.values]
GOOGLE_SOURCE = "google_routes"
SYNTHETIC_SOURCE = "synthetic"


@dataclass
class CalibrationReport:
    edges_calibrated: int = 0
    profiles_written: int = 0
    edges_skipped: list[tuple[str, str, str]] = field(default_factory=list)
    missing_profiles: list[tuple[str, str, str, str]] = field(default_factory=list)
    requests: int = 0
    elements: int = 0


def google_edges():
    return list(Edge.objects.filter(is_active=True, source=Edge.Source.GOOGLE).select_related("origin", "destination"))


def elements_needed() -> int:
    return len(google_edges()) * len(PROFILES)


def calibrate_from_google(
    client: RoutesClient, now: datetime | None = None, refresh: bool = False, progress=None,
) -> CalibrationReport:
    """Las muestras de Google se guardan en cuanto llegan (fuera de transacción): si el
    proceso se corta, al relanzarlo solo se pide lo que falta y no se paga dos veces.
    Solo la escritura de los multiplicadores es atómica."""
    now = now or timezone.now()
    report = CalibrationReport()
    edges = google_edges()
    for e in Edge.objects.filter(is_active=True).exclude(source=Edge.Source.GOOGLE).select_related("origin", "destination"):
        report.edges_skipped.append((e.origin.code, e.destination.code, "arista no verificada con Google"))

    nodes = {n.code: n for n in Node.objects.all()}
    pairs = [(e.origin.code, e.destination.code) for e in edges]
    samples = {}
    for band, day_type in PROFILES:
        samples[(band, day_type)] = fetch_samples(
            client, nodes, pairs, band=band, day_type=day_type,
            departure_time=representative_departure(band, day_type, now), traffic=True, refresh=refresh,
        )
        if progress:
            progress(band, day_type, client.requests_made)
    report.requests, report.elements = client.requests_made, client.elements_requested
    with transaction.atomic():
        _write_profiles(edges, samples, report)
    invalidate_graph()
    return report


def _write_profiles(edges, samples, report: CalibrationReport) -> None:
    calibrated_at = timezone.now()
    changed_edges, profiles = [], []
    for edge in edges:
        pair = (edge.origin.code, edge.destination.code)
        observed = {}
        candidates = [edge.duration_free_min * 60]
        for profile in PROFILES:
            sample = samples[profile].get(pair)
            if sample is None or not sample.ok:
                report.missing_profiles.append((*pair, *profile))
                continue
            observed[profile] = sample.duration_s
            candidates.append(sample.duration_s)
            if sample.static_duration_s:
                candidates.append(sample.static_duration_s)
        if not observed:
            report.edges_skipped.append((*pair, "Google no devolvió ningún perfil"))
            continue

        t0_s = min(candidates)
        edge.duration_free_min = t0_s / 60
        edge.updated_at = calibrated_at
        changed_edges.append(edge)
        for (band, day_type), duration_s in observed.items():
            profiles.append(TrafficProfile(
                edge=edge, band=band, day_type=day_type,
                # max() solo protege del redondeo de la división: duration_s ≥ t0_s siempre.
                multiplier=max(1.0, duration_s / t0_s),
                calibrated_at=calibrated_at, source=GOOGLE_SOURCE,
            ))
        report.edges_calibrated += 1

    # En lote: con Neon, una escritura por perfil (3,640) tarda demasiado.
    Edge.objects.bulk_update(changed_edges, ["duration_free_min", "updated_at"], batch_size=500)
    TrafficProfile.objects.bulk_create(
        profiles, batch_size=500, update_conflicts=True, unique_fields=["edge", "band", "day_type"],
        update_fields=["multiplier", "calibrated_at", "source"],
    )
    report.profiles_written += len(profiles)


# --- modo sintético (sin conexión) -----------------------------------------

CAPITAL_CODE = "ciudad-guatemala"
CAPITAL_RADIUS_KM = 30.0

# Multiplicadores base por franja: (cerca de la capital, resto del país)
SYNTHETIC_WEEKDAY = {
    TrafficBand.DAWN: (1.05, 1.0),
    TrafficBand.PEAK_AM: (1.6, 1.2),
    TrafficBand.MID_MORNING: (1.25, 1.1),
    TrafficBand.MIDDAY: (1.3, 1.1),
    TrafficBand.AFTERNOON: (1.3, 1.1),
    TrafficBand.PEAK_PM: (1.6, 1.2),
    TrafficBand.NIGHT: (1.0, 1.0),
}
SYNTHETIC_WEEKEND = {
    TrafficBand.DAWN: (1.0, 1.0),
    TrafficBand.PEAK_AM: (1.15, 1.05),
    TrafficBand.MID_MORNING: (1.2, 1.1),
    TrafficBand.MIDDAY: (1.25, 1.1),
    TrafficBand.AFTERNOON: (1.2, 1.1),
    TrafficBand.PEAK_PM: (1.25, 1.1),
    TrafficBand.NIGHT: (1.0, 1.0),
}
# En la capital, los picos son asimétricos: de mañana se ENTRA, de tarde se SALE.
PEAK_DIRECTION_BONUS = 0.15


def synthetic_multiplier(band: str, day_type: str, near_capital: bool, inbound: bool, rng: random.Random) -> float:
    table = SYNTHETIC_WEEKDAY if day_type == DayType.WEEKDAY else SYNTHETIC_WEEKEND
    base = table[band][0 if near_capital else 1]
    if near_capital and day_type == DayType.WEEKDAY:
        if band == TrafficBand.PEAK_AM:
            base += PEAK_DIRECTION_BONUS if inbound else -PEAK_DIRECTION_BONUS
        elif band == TrafficBand.PEAK_PM:
            base += -PEAK_DIRECTION_BONUS if inbound else PEAK_DIRECTION_BONUS
    return max(1.0, base + rng.uniform(-0.05, 0.05))


@transaction.atomic
def calibrate_synthetic(seed: int = 2026) -> CalibrationReport:
    """Perfiles sintéticos. Nunca pisa perfiles que vienen de Google."""
    report = CalibrationReport()
    rng = random.Random(seed)
    capital = Node.objects.get(code=CAPITAL_CODE)

    def to_capital(node: Node) -> float:
        return haversine_km(node.latitude, node.longitude, capital.latitude, capital.longitude)

    protected = set(
        TrafficProfile.objects.exclude(source=SYNTHETIC_SOURCE).values_list("edge_id", "band", "day_type")
    )
    calibrated_at = timezone.now()
    rows = []
    for edge in Edge.objects.filter(is_active=True).select_related("origin", "destination").order_by("id"):
        d_origin, d_destination = to_capital(edge.origin), to_capital(edge.destination)
        near_capital = min(d_origin, d_destination) <= CAPITAL_RADIUS_KM
        inbound = d_destination < d_origin
        for band, day_type in PROFILES:
            m = synthetic_multiplier(band, day_type, near_capital, inbound, rng)
            if (edge.id, band, day_type) in protected:
                continue
            rows.append(TrafficProfile(edge=edge, band=band, day_type=day_type, multiplier=m,
                                       calibrated_at=calibrated_at, source=SYNTHETIC_SOURCE))
        report.edges_calibrated += 1
    # Una sola sentencia: inserta o actualiza (SQLite y PostgreSQL).
    TrafficProfile.objects.bulk_create(
        rows, update_conflicts=True, unique_fields=["edge", "band", "day_type"],
        update_fields=["multiplier", "calibrated_at", "source"],
    )
    report.profiles_written = len(rows)
    invalidate_graph()
    return report
