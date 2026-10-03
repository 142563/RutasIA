/** Asignar, reasignar y cancelar rutas (RUT-35): tipos, hooks y textos de disponibilidad. */
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "./api";

export interface BusyRoute {
  id: number;
  code: string;
}

export interface DriverOption {
  id: number;
  name: string;
  phone: string;
  has_mobile_account: boolean;
  busy: boolean;
  busy_route: BusyRoute | null;
}

export interface VehicleOption {
  id: number;
  plate: string;
  model: string;
  capacity_kg: number;
  default_driver_id: number | null;
  default_driver: string | null;
  busy: boolean;
  busy_route: BusyRoute | null;
  /** null si se consultó sin ruta (no hay carga que comparar). */
  fits: boolean | null;
}

export interface AssignmentOptions {
  route_id: number | null;
  window: { start: string; end: string };
  total_weight_kg: number | null;
  drivers: DriverOption[];
  vehicles: VehicleOption[];
}

export interface AssignBody {
  driver_id?: number | null;
  vehicle_id?: number | null;
}

const kg = (value: number) => `${Math.round(value).toLocaleString("es-GT")} kg`;

/** Texto de disponibilidad de un piloto; null si está libre sin nada que avisar. */
export function driverNote(d: DriverOption): string | null {
  if (d.busy) return `Ocupado en ${d.busy_route?.code ?? "otra ruta"}`;
  if (!d.has_mobile_account) return "Sin cuenta en el celular";
  return null;
}

/** Un piloto ocupado no se puede elegir; sin cuenta sí (solo se avisa). */
export function driverDisabled(d: DriverOption): boolean {
  return d.busy;
}

export function vehicleNote(v: VehicleOption, totalKg: number | null): string | null {
  if (v.busy) return `Ocupado en ${v.busy_route?.code ?? "otra ruta"}`;
  if (v.fits === false && totalKg != null) return `No cabe: ${kg(totalKg)} > ${kg(v.capacity_kg)}`;
  return null;
}

export function vehicleDisabled(v: VehicleOption): boolean {
  return v.busy || v.fits === false;
}

/** Una ruta sin piloto no puede salir; es lo primero que el despachador debe resolver. */
export function isUnassigned(route: { driver: string | null; status: string }): boolean {
  return route.driver == null && (route.status === "planned" || route.status === "in_progress");
}

/** Solo las rutas planificadas se cambian o cancelan desde aquí. */
export function canManage(route: { status: string }): boolean {
  return route.status === "planned";
}

export function useAssignmentOptions(routeId: number | undefined, enabled = true) {
  return useQuery({
    queryKey: ["assignment-options", routeId],
    queryFn: () => api<AssignmentOptions>("/api/v2/assignment/options/", { query: { route_id: routeId } }),
    enabled: enabled && routeId != null,
    retry: false,
  });
}

function useInvalidate() {
  const client = useQueryClient();
  return () =>
    Promise.all(
      ["routes", "route", "assignment-options", "orders", "dashboard", "monitoring"].map((key) =>
        client.invalidateQueries({ queryKey: [key] }),
      ),
    );
}

export function useAssignRoute(routeId: number) {
  const invalidate = useInvalidate();
  return useMutation({
    mutationFn: (body: AssignBody) =>
      api<{ suggested_driver: boolean }>(`/api/v2/routes/${routeId}/assign/`, { method: "POST", body }),
    onSuccess: invalidate,
  });
}

export function useCancelRoute(routeId: number) {
  const invalidate = useInvalidate();
  return useMutation({
    mutationFn: (reason: string) =>
      api<{ released_orders: number }>(`/api/v2/routes/${routeId}/cancel/`, { method: "POST", body: { reason } }),
    onSuccess: invalidate,
  });
}
