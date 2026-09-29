"""Franjas horarias y tipo de día (docs/PLAN.md §2.3).

| Franja       | Horario     |
|--------------|-------------|
| dawn         | 05:00–07:00 |
| peak_am      | 07:00–09:00 |
| mid_morning  | 09:00–12:00 |
| midday       | 12:00–14:00 |
| afternoon    | 14:00–17:00 |
| peak_pm      | 17:00–20:00 |
| night        | 20:00–05:00 |  (cruza la medianoche)

Cada franja incluye su hora de inicio y excluye la de fin: 07:00 ya es pico mañana.
Guatemala no tiene horario de verano. Los feriados no se modelan: un feriado
entre semana se trata como día laboral (limitación documentada).
"""
from __future__ import annotations

from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from logistics.models import DayType, TrafficBand

GT_TZ = ZoneInfo("America/Guatemala")

# (hora de inicio, franja), en orden
BAND_STARTS = [
    (5, TrafficBand.DAWN),
    (7, TrafficBand.PEAK_AM),
    (9, TrafficBand.MID_MORNING),
    (12, TrafficBand.MIDDAY),
    (14, TrafficBand.AFTERNOON),
    (17, TrafficBand.PEAK_PM),
    (20, TrafficBand.NIGHT),
]

# Hora de salida representativa de cada franja para calibrar con Google:
# el punto medio, salvo la noche, donde se usa 23:00 (aún hay algo de tránsito).
REPRESENTATIVE_TIME = {
    TrafficBand.DAWN: time(6, 0),
    TrafficBand.PEAK_AM: time(8, 0),
    TrafficBand.MID_MORNING: time(10, 30),
    TrafficBand.MIDDAY: time(13, 0),
    TrafficBand.AFTERNOON: time(15, 30),
    TrafficBand.PEAK_PM: time(18, 30),
    TrafficBand.NIGHT: time(23, 0),
}

# Día representativo: martes (laboral) y sábado (fin de semana).
REPRESENTATIVE_WEEKDAY = {DayType.WEEKDAY: 1, DayType.WEEKEND: 5}


def to_local(moment: datetime) -> datetime:
    """Hora de Guatemala. Una fecha sin zona se interpreta como hora local."""
    if moment.tzinfo is None:
        return moment.replace(tzinfo=GT_TZ)
    return moment.astimezone(GT_TZ)


def band_for(moment: datetime) -> str:
    hour = to_local(moment).hour
    current = TrafficBand.NIGHT  # 00:00–04:59
    for start, band in BAND_STARTS:
        if hour >= start:
            current = band
    return current.value


def day_type_for(moment: datetime) -> str:
    return (DayType.WEEKEND if to_local(moment).weekday() >= 5 else DayType.WEEKDAY).value


def profile_for(moment: datetime) -> tuple[str, str]:
    return band_for(moment), day_type_for(moment)


def representative_departure(band: str, day_type: str, now: datetime) -> datetime:
    """Próxima salida FUTURA (al menos mañana) del perfil, en hora de Guatemala.

    Google exige que departureTime sea futuro para estimar el tráfico.
    """
    local_now = to_local(now)
    day: date = local_now.date() + timedelta(days=1)
    while day.weekday() != REPRESENTATIVE_WEEKDAY[day_type]:
        day += timedelta(days=1)
    return datetime.combine(day, REPRESENTATIVE_TIME[band], tzinfo=GT_TZ)
