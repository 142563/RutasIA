import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "./api";
import type { Band } from "./traffic";
import type { DataSource, NodeRef } from "./types";

export type Criterion = "time" | "distance";

export interface PlanStop {
  sequence: number;
  order_id: number;
  code: string;
  recipient: string;
  address: string;
  node: NodeRef | null;
  lat: number;
  lng: number;
  weight_kg: number;
  eta: string;
}

export interface PlanLeg {
  nodes: string[];
  roads: string[];
  minutes: number;
  km: number;
  unpaved_km: number;
  band: Band;
  depart_at: string;
  arrive_at: string;
  expanded: number;
}

export interface PlanVariant {
  criterion: Criterion;
  driving_minutes: number;
  total_km: number;
  finish_at: string;
  expanded: number;
  stops: PlanStop[];
  legs: PlanLeg[];
}

export interface DepartureOption {
  band: Band;
  band_label: string;
  departure: string;
  driving_minutes: number;
}

export interface PlanResponse {
  depot: { id: number; name: string; lat: number; lng: number; node: NodeRef | null };
  departure: string;
  band: Band;
  band_label: string;
  day_type: string;
  service_min: number;
  return_to_depot: boolean;
  total_weight_kg: number;
  fastest: PlanVariant;
  shortest: PlanVariant;
  minutes_saved: number;
  departure_options: DepartureOption[];
  data_source: DataSource;
}

export interface PlanRequest {
  depot_id: number;
  order_ids: number[];
  departure: string;
  service_min: number;
  return_to_depot: boolean;
  allow_unpaved?: boolean;
}

export function usePlan(request: PlanRequest | null) {
  return useQuery({
    queryKey: ["plan", request],
    queryFn: () => api<PlanResponse>("/api/v2/routes/plan/", { method: "POST", body: request }),
    enabled: request !== null && request.order_ids.length > 0,
    placeholderData: (previous) => previous,
    retry: false,
  });
}

export function useCreateRoute() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (body: PlanRequest & { criterion: Criterion; driver_id?: number; vehicle_id?: number }) =>
      api<{ route: { code: string; driving_minutes: number } }>("/api/v2/routes/", { method: "POST", body }),
    onSuccess: () => {
      client.invalidateQueries({ queryKey: ["orders"] });
      client.invalidateQueries({ queryKey: ["routes"] });
    },
  });
}

export interface DriverOption { id: number; name: string; is_active: boolean }
export interface VehicleOption { id: number; plate: string; model: string; capacity_kg: number; is_active: boolean; driver_id: number | null }

export function useFleet() {
  // El despachador puede consultar la flota por /api/v2/fleet/ (solo lectura).
  const drivers = useQuery({
    queryKey: ["fleet", "drivers"],
    queryFn: async () => (await api<{ drivers: { id: number; name: string; is_active: boolean }[] }>("/api/v2/fleet/drivers/")).drivers,
  });
  const vehicles = useQuery({
    queryKey: ["fleet", "vehicles"],
    queryFn: async () =>
      (await api<{ vehicles: { id: number; plate: string; model: string; capacity_kg: number; is_active: boolean; driver: { id: number } | null }[] }>("/api/v2/fleet/vehicles/")).vehicles,
  });
  return {
    drivers: (drivers.data ?? []).filter((d) => d.is_active) as DriverOption[],
    vehicles: (vehicles.data ?? []).filter((v) => v.is_active).map((v): VehicleOption => ({ ...v, driver_id: v.driver?.id ?? null })),
  };
}

/** Nodos de toda la ruta (tramos concatenados sin repetir el nodo de unión). */
export function routeNodes(variant: PlanVariant): string[] {
  const codes: string[] = [];
  for (const leg of variant.legs) {
    for (const code of leg.nodes) if (codes[codes.length - 1] !== code) codes.push(code);
  }
  return codes;
}
