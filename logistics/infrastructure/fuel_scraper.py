"""
Scraper de precios de combustible para Guatemala.

Estrategia de fuentes (se intenta en orden):
  1. mem.gob.gt — fuente oficial del MEM (bloqueada por Cloudflare sin navegador real)
  2. globalpetrolprices.com — precios semanales en GTQ/litro, convertidos a GTQ/galón

Si todas las fuentes fallan, se lanza ValueError con detalle de errores.
"""

import logging
import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

import httpx
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

# Rango válido para precios de combustible en GTQ/galón en Guatemala
_GTQ_GAL_MIN = 15.0
_GTQ_GAL_MAX = 80.0

# Rango válido para GTQ/litro (antes de convertir a galón)
_GTQ_LIT_MIN = 5.0
_GTQ_LIT_MAX = 25.0

_LITERS_PER_GALLON = Decimal("3.78541")

_BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "es-GT,es;q=0.9,en;q=0.8",
    "Accept-Encoding": "gzip, deflate, br",
    "Cache-Control": "no-cache",
}


@dataclass
class FuelPrices:
    regular: Decimal
    super_: Decimal
    diesel: Decimal
    source_url: str


# ---------------------------------------------------------------------------
# Punto de entrada público
# ---------------------------------------------------------------------------

def fetch_mem_fuel_prices() -> FuelPrices:
    """
    Obtiene precios de combustible actuales en GTQ/galón para Guatemala.

    Intenta varias fuentes en orden y retorna la primera exitosa.

    Raises:
        ValueError: si ninguna fuente retornó precios válidos.
    """
    sources = [
        ("MEM Guatemala", _try_mem),
        ("GlobalPetrolPrices", _try_global_petrol_prices),
    ]

    errors: list[str] = []
    for name, fn in sources:
        try:
            prices = fn()
            if prices:
                logger.info(
                    "Precios obtenidos de %s — Regular Q%.2f | Super Q%.2f | Diesel Q%.2f",
                    name, prices.regular, prices.super_, prices.diesel,
                )
                return prices
            errors.append(f"{name}: no se encontraron precios válidos en la página")
        except Exception as exc:
            logger.warning("Fuente %s falló: %s", name, exc)
            errors.append(f"{name}: {exc}")

    raise ValueError(
        "No se pudo obtener precios de ninguna fuente.\n" + "\n".join(errors)
    )


# ---------------------------------------------------------------------------
# Fuente 1: mem.gob.gt (oficial — requiere navegador real para pasar Cloudflare)
# ---------------------------------------------------------------------------

_MEM_URLS = [
    "https://www.mem.gob.gt/hidrocarburos/precios-de-combustibles/",
    "https://mem.gob.gt/hidrocarburos/precios-de-combustibles/",
]


def _try_mem() -> FuelPrices | None:
    for url in _MEM_URLS:
        try:
            with httpx.Client(timeout=20.0, follow_redirects=True) as client:
                response = client.get(url, headers=_BROWSER_HEADERS)
                response.raise_for_status()

            soup = BeautifulSoup(response.text, "html.parser")
            prices = _parse_table_gtq_gal(soup, url) or _parse_text_gtq_gal(
                soup.get_text(" ", strip=True), url
            )
            if prices:
                return prices
        except Exception as exc:
            logger.debug("MEM URL %s → %s", url, exc)

    return None


# ---------------------------------------------------------------------------
# Fuente 2: globalpetrolprices.com (Guatemala, datos semanales)
# ---------------------------------------------------------------------------

_GPP_GAS_URL = "https://www.globalpetrolprices.com/Guatemala/gasoline_prices/"
_GPP_DIESEL_URL = "https://www.globalpetrolprices.com/Guatemala/diesel_prices/"


def _try_global_petrol_prices() -> FuelPrices | None:
    """
    Extrae precios en GTQ/Litro de GlobalPetrolPrices y los convierte a GTQ/galón.

    La tabla 1 de cada página tiene la columna "Price (GTQ/Liter)" con
    la fila "Current price" como primer registro de datos.
    Super gasolina no está disponible; se estima como regular × 1.08.
    """
    with httpx.Client(timeout=20.0, follow_redirects=True) as client:
        gas_resp = client.get(_GPP_GAS_URL, headers=_BROWSER_HEADERS)
        gas_resp.raise_for_status()
        diesel_resp = client.get(_GPP_DIESEL_URL, headers=_BROWSER_HEADERS)
        diesel_resp.raise_for_status()

    gas_gtq_l = _extract_gpp_current_price(gas_resp.text)
    diesel_gtq_l = _extract_gpp_current_price(diesel_resp.text)

    if gas_gtq_l is None or diesel_gtq_l is None:
        return None

    regular_gal = (gas_gtq_l * _LITERS_PER_GALLON).quantize(Decimal("0.01"))
    super_gal = (regular_gal * Decimal("1.08")).quantize(Decimal("0.01"))
    diesel_gal = (diesel_gtq_l * _LITERS_PER_GALLON).quantize(Decimal("0.01"))

    return FuelPrices(
        regular=regular_gal,
        super_=super_gal,
        diesel=diesel_gal,
        source_url=_GPP_GAS_URL,
    )


def _extract_gpp_current_price(html: str) -> Decimal | None:
    """
    Extrae el precio "Current price" en GTQ/Litro desde la página de
    GlobalPetrolPrices.

    Estructura esperada (Tabla 1):
      | Encabezado        | Price (GTQ/Liter) | Percent change |
      | Current price     | 10.44             | -              |
      | One month ago     | ...               | ...            |
    """
    soup = BeautifulSoup(html, "html.parser")

    for table in soup.find_all("table"):
        table_text = table.get_text()
        if "GTQ" not in table_text:
            continue

        for row in table.find_all("tr"):
            cells = row.find_all(["td", "th"])
            if len(cells) < 2:
                continue
            label = cells[0].get_text(strip=True).lower()
            if "current" in label:
                price = _to_decimal_liter(cells[1].get_text(strip=True))
                if price is not None:
                    return price

    return None


# ---------------------------------------------------------------------------
# Helpers de parseo (MEM)
# ---------------------------------------------------------------------------

def _parse_table_gtq_gal(soup: BeautifulSoup, source_url: str) -> FuelPrices | None:
    """Extrae precios en GTQ/galón de una tabla HTML del MEM."""
    regular = super_ = diesel = None

    for table in soup.find_all("table"):
        for row in table.find_all("tr"):
            cells = row.find_all(["td", "th"])
            if not cells:
                continue
            row_text = " ".join(c.get_text(strip=True) for c in cells).lower()
            prices = [_to_decimal_gal(c.get_text(strip=True)) for c in cells]
            prices = [p for p in prices if p is not None]
            if not prices:
                continue
            if "regular" in row_text and regular is None:
                regular = prices[-1]
            elif "super" in row_text and super_ is None:
                super_ = prices[-1]
            elif "diesel" in row_text and diesel is None:
                diesel = prices[-1]
        if all(p is not None for p in [regular, super_, diesel]):
            return FuelPrices(regular=regular, super_=super_, diesel=diesel, source_url=source_url)

    return None


_TEXT_PATTERNS = {
    "regular": re.compile(r"regular[^0-9]{0,40}?(\d{2,3}[.,]\d{2})", re.IGNORECASE),
    "super_": re.compile(r"super[^0-9]{0,40}?(\d{2,3}[.,]\d{2})", re.IGNORECASE),
    "diesel": re.compile(r"diesel[^0-9]{0,40}?(\d{2,3}[.,]\d{2})", re.IGNORECASE),
}


def _parse_text_gtq_gal(text: str, source_url: str) -> FuelPrices | None:
    """Extrae precios usando regex sobre el texto de la página."""
    found: dict[str, Decimal] = {}
    for key, pattern in _TEXT_PATTERNS.items():
        match = pattern.search(text)
        if match:
            price = _to_decimal_gal(match.group(1))
            if price is not None:
                found[key] = price
    if len(found) == 3:
        return FuelPrices(source_url=source_url, **found)  # type: ignore[arg-type]
    return None


# ---------------------------------------------------------------------------
# Utilidades de conversión
# ---------------------------------------------------------------------------

def _to_decimal_gal(text: str) -> Decimal | None:
    """Convierte texto a Decimal si está en rango de GTQ/galón válido."""
    return _parse_number(text, _GTQ_GAL_MIN, _GTQ_GAL_MAX)


def _to_decimal_liter(text: str) -> Decimal | None:
    """Convierte texto a Decimal si está en rango de GTQ/litro válido."""
    return _parse_number(text, _GTQ_LIT_MIN, _GTQ_LIT_MAX)


def _parse_number(text: str, min_val: float, max_val: float) -> Decimal | None:
    raw = re.sub(r"[^\d.,]", "", text).replace(",", ".")
    parts = raw.split(".")
    if len(parts) > 2:
        raw = "".join(parts[:-1]) + "." + parts[-1]
    try:
        value = Decimal(raw)
        if min_val <= float(value) <= max_val:
            return value
    except (InvalidOperation, ValueError):
        pass
    return None
