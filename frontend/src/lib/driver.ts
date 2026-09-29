import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "./api";
import type { NodeRef } from "./types";

export type StopStatus = "pending" | "delivered" | "failed";
export type DriverRouteStatus = "planned" | "in_progress" | "completed" | "canceled";

export interface DriverStop {
  id: number;
  sequence: number;
  order_code: string;
  recipient: string;
  phone: string;
  address: string;
  lat: number | null;
  lng: number | null;
  node: NodeRef | null;
  eta: string;
  status: StopStatus;
  status_label: string;
  reason: string;
  delivered_at: string | null;
}

export interface DriverRoute {
  id: number;
  code: string;
  status: DriverRouteStatus;
  status_label: string;
  depot: string;
  vehicle: string | null;
  departure_at: string;
  finish_at: string;
  started_at: string | null;
  completed_at: string | null;
  driving_minutes: number;
  total_km: number;
  data_source: string;
  stops: DriverStop[];
}

export interface DriverToday {
  driver: { id: number; name: string; phone: string };
  date: string;
  routes: DriverRoute[];
}

export const REASONS = ["Cliente ausente", "Dirección incorrecta", "Rechazó el paquete", "Negocio cerrado"] as const;

const TODAY_KEY = ["driver", "today"];

export function useDriverToday() {
  return useQuery({
    queryKey: TODAY_KEY,
    queryFn: () => api<DriverToday>("/api/driver/today/"),
    // El despachador puede reasignar rutas: se refresca al volver a la app
    refetchOnWindowFocus: true,
    retry: false,
  });
}

export function useStartRoute() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (routeId: number) => api<{ route: DriverRoute }>(`/api/driver/routes/${routeId}/start/`, { method: "POST", body: {} }),
    onSuccess: () => client.invalidateQueries({ queryKey: TODAY_KEY }),
  });
}

export function useUpdateStop() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (v: { stopId: number; status: "delivered" | "failed"; reason?: string }) =>
      api<{ route: DriverRoute; stop_id: number }>(`/api/driver/stops/${v.stopId}/`, {
        method: "POST",
        body: { status: v.status, reason: v.reason },
      }),
    onSuccess: () => client.invalidateQueries({ queryKey: TODAY_KEY }),
  });
}

/** Avance de una ruta: paradas ya marcadas (entregadas o no) sobre el total. */
export function routeProgress(route: Pick<DriverRoute, "stops">) {
  const total = route.stops.length;
  const delivered = route.stops.filter((s) => s.status === "delivered").length;
  const failed = route.stops.filter((s) => s.status === "failed").length;
  const done = delivered + failed;
  return { total, delivered, failed, done, percent: total ? Math.round((done / total) * 100) : 0 };
}

/** La próxima parada pendiente, en orden de recorrido. */
export function nextStop(route: Pick<DriverRoute, "stops">): DriverStop | undefined {
  return [...route.stops].sort((a, b) => a.sequence - b.sequence).find((s) => s.status === "pending");
}

export function findStop(data: DriverToday | undefined, stopId: number): { route: DriverRoute; stop: DriverStop } | null {
  for (const route of data?.routes ?? []) {
    const stop = route.stops.find((s) => s.id === stopId);
    if (stop) return { route, stop };
  }
  return null;
}

export function navigationUrl(stop: Pick<DriverStop, "lat" | "lng">): string | null {
  if (stop.lat == null || stop.lng == null) return null;
  return `https://www.google.com/maps/dir/?api=1&destination=${stop.lat},${stop.lng}`;
}

export function telUrl(phone: string): string | null {
  const digits = phone.replace(/[^\d+]/g, "");
  return digits ? `tel:${digits}` : null;
}
