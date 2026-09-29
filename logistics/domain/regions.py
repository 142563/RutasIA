"""Regiones de Guatemala (regionalización oficial de 8 regiones).

Sirven para agrupar pedidos cercanos: planificar "todo Occidente" en un clic da una
ruta con sentido, en lugar de mezclar entregas de todo el país.
"""
from __future__ import annotations

REGIONS: dict[str, str] = {
    "I": "Metropolitana",
    "II": "Norte",
    "III": "Nororiente",
    "IV": "Suroriente",
    "V": "Central",
    "VI": "Suroccidente",
    "VII": "Noroccidente",
    "VIII": "Petén",
}

# Código de departamento (logistics.models.GuatemalaDepartment) -> región
DEPARTMENT_REGION: dict[str, str] = {
    "GU": "I",
    "AV": "II", "BV": "II",
    "IZ": "III", "CQ": "III", "ZA": "III", "PR": "III",
    "SR": "IV", "JA": "IV", "JU": "IV",
    "SA": "V", "CM": "V", "ES": "V",
    "SO": "VI", "TO": "VI", "QZ": "VI", "SU": "VI", "RE": "VI", "SM": "VI",
    "HU": "VII", "QC": "VII",
    "PE": "VIII",
}


def region_of(department: str | None) -> dict | None:
    code = DEPARTMENT_REGION.get(department or "")
    return {"code": code, "name": REGIONS[code]} if code else None
