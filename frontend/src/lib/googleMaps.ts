import { useQuery } from "@tanstack/react-query";
import * as React from "react";
import { api } from "./api";

/**
 Carga del mapa base de Google Maps (Maps JavaScript API).

 La key del navegador llega de Django en /api/config/ (restringida por HTTP referrer).
 Si no hay key, o Google la rechaza, la app sigue con el mapa esquemático propio:
 Google solo aporta el fondo y el dibujo por carretera, el algoritmo es nuestro.
*/

interface ClientConfig {
  google_maps_api_key: string;
  google_maps_map_id: string;
}

export type GoogleMapsStatus = "loading" | "ready" | "unavailable";

let loader: Promise<void> | null = null;

function loadScript(key: string): Promise<void> {
  if (window.google?.maps?.Map) return Promise.resolve();
  if (loader) return loader;
  loader = new Promise<void>((resolve, reject) => {
    const w = window as unknown as Record<string, unknown>;
    w.__rutasiaMapsReady = () => resolve();
    // Google llama a esta función si la key es inválida, está restringida a otro dominio
    // o el proyecto no tiene facturación.
    w.gm_authFailure = () => {
      authFailed = true;
      listeners.forEach((fn) => fn());
    };
    const script = document.createElement("script");
    const params = new URLSearchParams({ key, v: "weekly", loading: "async", callback: "__rutasiaMapsReady", language: "es", region: "GT" });
    script.src = `https://maps.googleapis.com/maps/api/js?${params}`;
    script.async = true;
    script.onerror = () => reject(new Error("No se pudo descargar Google Maps."));
    document.head.appendChild(script);
  });
  loader.catch(() => { loader = null; });
  return loader;
}

let authFailed = false;
const listeners = new Set<() => void>();

/** Estado del mapa base de Google para esta sesión del navegador. */
export function useGoogleMaps(): { status: GoogleMapsStatus; reason?: string } {
  const query = useQuery({
    queryKey: ["google-maps"],
    queryFn: async () => {
      const { google_maps_api_key: key } = await api<ClientConfig>("/api/config/");
      if (!key) return { ok: false as const, reason: "Falta GOOGLE_MAPS_API_KEY en el servidor." };
      await loadScript(key);
      return { ok: true as const };
    },
    staleTime: Infinity,
    retry: false,
  });
  // Re-renderiza si Google avisa después que la key no sirve
  const [, force] = React.useReducer((x: number) => x + 1, 0);
  React.useEffect(() => {
    const fn = () => force();
    listeners.add(fn);
    return () => { listeners.delete(fn); };
  }, []);

  if (authFailed) return { status: "unavailable", reason: "Google rechazó la key (revisa restricciones de dominio y facturación)." };
  if (query.isPending) return { status: "loading" };
  if (query.error) return { status: "unavailable", reason: query.error.message };
  if (!query.data.ok) return { status: "unavailable", reason: query.data.reason };
  return { status: "ready" };
}
