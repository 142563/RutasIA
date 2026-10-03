import * as React from "react";
import type { LatLng } from "./geo";

/**
 Autocompletado de direcciones con Google Places (New), restringido a Guatemala.

 Se usa `google.maps.places.AutocompleteSuggestion` (la clase de Places API (New) de la
 librería "places" del Maps JS API) en lugar del `Autocomplete` clásico, que Google ya no
 ofrece a cuentas nuevas. El detalle se pide con `Place.fetchFields`, y ambos comparten el
 mismo `AutocompleteSessionToken` para que la búsqueda se cobre como una sola sesión.
 Todo es opcional: si Google no carga o falla, las funciones devuelven vacío y el formulario
 sigue con la entrada manual.
*/

export interface PlaceSuggestion {
  placeId: string;
  /** Texto principal (p. ej. "5a avenida 10-20") */
  main: string;
  /** Texto secundario (zona, municipio) */
  secondary: string;
  /** Texto completo de la sugerencia */
  text: string;
}

export interface ChosenPlace extends LatLng {
  placeId: string;
  address: string;
}

export const DEBOUNCE_MS = 300;
export const MIN_QUERY_CHARS = 3;

/** ¿Vale la pena consultar a Google con este texto? */
export function shouldSearch(query: string): boolean {
  return query.trim().length >= MIN_QUERY_CHARS;
}

type Text = { text?: string } | string | undefined | null;

interface RawSuggestion {
  placePrediction?: { placeId?: string; text?: Text; mainText?: Text; secondaryText?: Text } | null;
}

const asText = (value: Text): string => (typeof value === "string" ? value : value?.text ?? "");

/** Convierte las sugerencias crudas de Google; descarta las que no son lugares (consultas). */
export function parseSuggestions(raw: RawSuggestion[]): PlaceSuggestion[] {
  const out: PlaceSuggestion[] = [];
  for (const item of raw) {
    const p = item.placePrediction;
    if (!p?.placeId) continue;
    const text = asText(p.text);
    const main = asText(p.mainText) || text;
    out.push({ placeId: p.placeId, main, secondary: asText(p.secondaryText), text: text || main });
  }
  return out;
}

interface RawPlace {
  id?: string | null;
  formattedAddress?: string | null;
  displayName?: string | null;
  location?: { lat: number | (() => number); lng: number | (() => number) } | null;
}

const coord = (v: number | (() => number)): number => (typeof v === "function" ? v() : v);

/** Convierte el lugar detallado de Google en el que guarda el pedido. null si no trae coordenadas. */
export function parsePlace(place: RawPlace, fallbackId = "", fallbackText = ""): ChosenPlace | null {
  if (!place.location) return null;
  const lat = coord(place.location.lat);
  const lng = coord(place.location.lng);
  if (!Number.isFinite(lat) || !Number.isFinite(lng)) return null;
  const address = (place.formattedAddress || fallbackText || place.displayName || "").trim();
  return { lat, lng, placeId: place.id || fallbackId, address };
}

type PlacesLib = typeof google.maps.places;

async function placesLibrary(): Promise<PlacesLib | null> {
  try {
    if (!window.google?.maps?.importLibrary) return null;
    return (await google.maps.importLibrary("places")) as PlacesLib;
  } catch {
    return null;
  }
}

/** Sugerencias para el texto escrito. Devuelve [] si Google no está disponible o falla. */
export async function fetchSuggestions(input: string, token: google.maps.places.AutocompleteSessionToken | null): Promise<PlaceSuggestion[]> {
  if (!shouldSearch(input)) return [];
  const lib = await placesLibrary();
  if (!lib) return [];
  try {
    const { suggestions } = await lib.AutocompleteSuggestion.fetchAutocompleteSuggestions({
      input,
      ...(token ? { sessionToken: token } : {}),
      includedRegionCodes: ["gt"],
      language: "es",
      region: "gt",
    });
    return parseSuggestions(suggestions as unknown as RawSuggestion[]);
  } catch {
    return [];
  }
}

/** Detalle (dirección formateada, lat/lng y place_id) de la sugerencia elegida. */
export async function fetchPlace(suggestion: PlaceSuggestion): Promise<ChosenPlace | null> {
  const lib = await placesLibrary();
  if (!lib) return null;
  try {
    const place = new lib.Place({ id: suggestion.placeId });
    await place.fetchFields({ fields: ["id", "formattedAddress", "location", "displayName"] });
    return parsePlace(place as unknown as RawPlace, suggestion.placeId, suggestion.text);
  } catch {
    return null;
  }
}

/** Token de sesión: uno por búsqueda completa (se renueva al elegir una sugerencia). */
export async function newSessionToken(): Promise<google.maps.places.AutocompleteSessionToken | null> {
  const lib = await placesLibrary();
  return lib ? new lib.AutocompleteSessionToken() : null;
}

/** Valor que se actualiza solo tras `ms` sin cambios (debounce). */
export function useDebounced<T>(value: T, ms = DEBOUNCE_MS): T {
  const [debounced, setDebounced] = React.useState(value);
  React.useEffect(() => {
    const id = window.setTimeout(() => setDebounced(value), ms);
    return () => window.clearTimeout(id);
  }, [value, ms]);
  return debounced;
}
