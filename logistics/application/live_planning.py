"""Tráfico en vivo al planificar (híbrido, decisión de Julio del 2026-10-14).

1. El motor planifica como siempre: matriz con Dijkstra y perfiles calibrados por
   franja, orden con el algoritmo genético y cada tramo con A*.
2. Después, Google mide EN VIVO cada tramo elegido: una consulta computeRoutes por
   tramo, con tráfico (TRAFFIC_AWARE_OPTIMAL), pasando por los nodos de nuestro A*
   como puntos intermedios (hasta 25, límite de Google), a la hora en que sale ese
   tramo. Así Google mide NUESTRA ruta, no la suya.
3. Los minutos y las llegadas de la ruta se recalculan con esas duraciones.

Google nunca se llama dentro de Dijkstra ni de A*. Si no hay llave, si Google falla
o tarda más de LIVE_TRAFFIC_TIMEOUT_S, o si se llegó al tope diario, la ruta queda
con los perfiles calibrados y lo dice (`perfil_calibrado`). Nunca se mezclan tramos
en vivo con tramos calibrados.
"""
from __future__ import annotations

import concurrent.futures as futures
import hashlib
import time
from dataclasses import dataclass
from datetime import datetime, timedelta

from django.conf import settings
from django.core.cache import cache
from django.utils import timezone

from logistics.routing.google import RoutesApiError, RoutesClient
from logistics.routing.graph import RoadGraph
from logistics.routing.multistop import MultiStopPlan

LIVE = "google_tiempo_real"
CALIBRATED = "perfil_calibrado"
CACHE_SECONDS = 300  # 5 minutos por tramo y franja de salida de 5 minutos
WORKERS = 8
MIN_LEAD = timedelta(seconds=15)  # Google no acepta una hora de salida ya pasada


@dataclass
class TrafficSource:
    source: str  # google_tiempo_real | perfil_calibrado
    queried_at: datetime | None = None
    requests: int = 0  # consultas nuevas a Google (las de caché no cuentan)
    reason: str = ""  # por qué se usaron los perfiles calibrados

    def payload(self) -> dict:
        return {
            "traffic_source": self.source,
            "traffic_queried_at": self.queried_at.isoformat() if self.queried_at else None,
            "traffic_note": self.reason,
        }


def calibrated(reason: str) -> TrafficSource:
    return TrafficSource(CALIBRATED, reason=reason)


def _daily_key(now: datetime) -> str:
    return f"live-traffic-requests:{timezone.localtime(now).date().isoformat()}"


def _leg_key(codes: list[str], depart: datetime) -> str:
    digest = hashlib.sha1(">".join(codes).encode()).hexdigest()[:16]
    return f"live-leg:{digest}:{int(depart.timestamp() // CACHE_SECONDS)}"


def apply_live_traffic(graph: RoadGraph, plans: list[MultiStopPlan], client: RoutesClient | None = None,
                       now: datetime | None = None) -> TrafficSource:
    """Reemplaza los minutos de cada tramo por los de Google en vivo (todos o ninguno).

    `plans` = las variantes que se comparan entre sí (más rápida y más corta), para que
    la comparación use la misma fuente. Modifica los planes solo si todo salió bien.
    """
    if not settings.LIVE_TRAFFIC:
        return calibrated("El tráfico en vivo está desactivado.")
    # Import local: live_traffic → incidents → planning (evita el import circular)
    from logistics.application.live_traffic import sample_intermediates

    plans = list({id(plan): plan for plan in plans}.values())  # la más rápida puede ser la más corta
    now = now or timezone.now()
    if client is None:
        try:
            client = RoutesClient(timeout=settings.LIVE_TRAFFIC_TIMEOUT_S)
        except RoutesApiError:
            return calibrated("Falta la llave de Google del servidor.")

    # Tramos únicos a medir (las dos variantes suelen compartir tramos)
    wanted: dict[str, tuple[list[str], datetime]] = {}
    for plan in plans:
        for leg in plan.legs:
            codes = [graph.codes[i] for i in leg.search.path]
            depart = max(leg.depart_at, now + MIN_LEAD)
            wanted.setdefault(_leg_key(codes, depart), (codes, depart))
    minutes = {key: cache.get(key) for key in wanted}
    missing = [key for key, value in minutes.items() if value is None]

    used = cache.get(_daily_key(now), 0)
    if used + len(missing) > settings.LIVE_TRAFFIC_DAILY_REQUESTS:
        return calibrated("Se alcanzó el tope diario de consultas a Google.")

    def point(code: str) -> tuple[float, float]:
        i = graph.index[code]
        return graph.lat[i], graph.lon[i]

    def fetch(key: str) -> tuple[str, float]:
        codes, depart = wanted[key]
        result = client.compute_route(point(codes[0]), point(codes[-1]),
                                      [point(c) for c in sample_intermediates(codes)],
                                      departure_time=depart, traffic=True, geometry=False)
        return key, result.duration_s / 60

    if missing:
        deadline = time.monotonic() + settings.LIVE_TRAFFIC_TIMEOUT_S
        pool = futures.ThreadPoolExecutor(max_workers=WORKERS)
        try:
            jobs = [pool.submit(fetch, key) for key in missing]
            for job in futures.as_completed(jobs, timeout=max(0.1, deadline - time.monotonic())):
                key, value = job.result()
                minutes[key] = value
                cache.set(key, value, CACHE_SECONDS)
        except futures.TimeoutError:
            return calibrated("Google tardó demasiado en responder.")
        except (RoutesApiError, OSError, ValueError):
            return calibrated("Google no respondió; se usaron los perfiles calibrados.")
        finally:
            pool.shutdown(wait=False, cancel_futures=True)
            cache.set(_daily_key(now), used + len(missing), 60 * 60 * 26)

    # Todo llegó: se recalculan minutos y llegadas, encadenando el tiempo de servicio
    for plan in plans:
        current = plan.departure
        etas = []
        for position, leg in enumerate(plan.legs):
            codes = [graph.codes[i] for i in leg.search.path]
            key = _leg_key(codes, max(leg.depart_at, now + MIN_LEAD))
            leg.minutes = minutes[key]
            leg.depart_at = current
            leg.arrive_at = current + timedelta(minutes=leg.minutes)
            is_stop = position < len(plan.order)
            if is_stop:
                etas.append(leg.arrive_at)
            current = leg.arrive_at + timedelta(minutes=plan.service_min if is_stop else 0)
        plan.etas = etas
    return TrafficSource(LIVE, queried_at=now, requests=len(missing))
