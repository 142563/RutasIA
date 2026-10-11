import { useQueries } from "@tanstack/react-query";
import { api } from "./api";
import type { LatLng } from "./geo";

export interface VehiclePosition extends LatLng {
  id: number; recorded_at: string; speed_kmh: number | null; heading: number | null;
  accuracy_m: number | null; source: "phone" | "tracker";
}
export interface PositionTrace { route_id: number; latest: VehiclePosition | null; positions: VehiclePosition[] }

export function useVehicleTracking(routes: { id: number; code: string; status: string }[]) {
  const active = routes.filter((route) => route.status === "in_progress");
  const queries = useQueries({ queries: active.map((route) => ({
    queryKey: ["vehicle-positions", route.id],
    queryFn: () => api<PositionTrace>(`/api/v2/routes/${route.id}/positions/`),
    refetchInterval: 10_000, retry: false,
  })) });
  return { vehicles: queries.flatMap((query, index) => query.data?.latest ? [{
    id: String(active[index].id), label: active[index].code,
    position: query.data.latest, trace: query.data.positions,
  }] : []), failed: queries.some((query) => query.isError) };
}
