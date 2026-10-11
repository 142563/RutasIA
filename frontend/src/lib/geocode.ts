import type { LatLng } from "./geo";
import { shouldSearch } from "./places";

/**
 Geocodificación de la dirección escrita a mano (Google Geocoder, restringido a Guatemala).

 Se usa cuando la persona escribe la dirección y no elige ninguna sugerencia de Places: al salir
 del campo se busca el punto y se coloca solo. La lógica de decisión es pura (`shouldGeocode`) y
 el acceso a Google queda aislado en `geocodeAddress`, que devuelve null si algo falla.
*/

/** De dónde salió la ubicación actual del formulario. */
export type LocationSource = "place" | "geocode" | "node" | "map";

export interface GeocodedAddress extends LatLng {
  address: string;
}

/**
 ¿Hay que geocodificar al salir del campo?
 - No si el texto es muy corto.
 - No si la persona ya fijó el punto a mano (municipio o clic en el mapa).
 - No si la ubicación viene de una sugerencia de Places o de una búsqueda previa y el texto no cambió.
*/
export function shouldGeocode(args: {
  address: string;
  source: LocationSource | null;
  /** Texto con el que se fijó la ubicación actual (place o geocode). */
  locatedFor: string;
}): boolean {
  const text = args.address.trim();
  if (!shouldSearch(text)) return false;
  if (args.source === "node" || args.source === "map") return false;
  if ((args.source === "place" || args.source === "geocode") && text === args.locatedFor.trim()) return false;
  return true;
}

interface RawGeocodeResult {
  formatted_address?: string;
  geometry?: { location?: { lat: number | (() => number); lng: number | (() => number) } | null } | null;
}

const coord = (v: number | (() => number)): number => (typeof v === "function" ? v() : v);

/** Toma el primer resultado con coordenadas válidas. */
export function parseGeocode(results: RawGeocodeResult[] | null | undefined, fallbackText = ""): GeocodedAddress | null {
  for (const r of results ?? []) {
    const loc = r.geometry?.location;
    if (!loc) continue;
    const lat = coord(loc.lat);
    const lng = coord(loc.lng);
    if (!Number.isFinite(lat) || !Number.isFinite(lng)) continue;
    return { lat, lng, address: (r.formatted_address || fallbackText).trim() };
  }
  return null;
}

/** Busca la dirección en Guatemala. null si Google no está disponible o no la encuentra. */
export async function geocodeAddress(address: string): Promise<GeocodedAddress | null> {
  try {
    if (!window.google?.maps?.importLibrary) return null;
    const lib = (await google.maps.importLibrary("geocoding")) as google.maps.GeocodingLibrary;
    const { results } = await new lib.Geocoder().geocode({
      address,
      region: "GT",
      componentRestrictions: { country: "GT" },
    });
    return parseGeocode(results as unknown as RawGeocodeResult[], address);
  } catch {
    return null;
  }
}
