/** Tipos y hooks de Rutas, Monitoreo, Inicio y Reportes (RUT-16). */
import { useQuery } from "@tanstack/react-query";
import { api } from "./api";
import type { NodeRef } from "./types";

export type RouteStatus = "planned" | "in_progress" | "completed" | "canceled";
export type StopStatus = "pending" | "delivered" | "failed";
/** Cómo va una parada frente a su ETA (la tolerancia la define el servidor). */
export type StopTiming = "on_time" | "late" | "overdue" | "pending" | "failed";

export const ROUTE_STATUS: Record<RouteStatus, { label: string; color: string }> = {
  planned: { label: "Planificada", color: "#2f4bd8" },
  in_progress: { label: "En curso", color: "#b45309" },
  completed: { label: "Completada", color: "#1a7f4b" },
  canceled: { label: "Cancelada", color: "#6b6f76" },
};

export const TIMING: Record<StopTiming, { label: string; color: string }> = {
  on_time: { label: "A tiempo", color: "#1a7f4b" },
  late: { label: "Con retraso", color: "#b45309" },
  overdue: { label: "Retrasada", color: "#b45309" },
  pending: { label: "Pendiente", color: "#a3a6ac" },
  failed: { label: "No entregada", color: "#b42318" },
};

export interface Progress {
  delivered: number;
  failed: number;
  total: number;
}

export interface RouteStopRow {
  id: number;
  sequence: number;
  order_code: string;
  recipient: string;
  phone: string;
  address: string;
  node: NodeRef | null;
  eta: string;
  status: StopStatus;
  status_label: string;
  reason: string;
  delivered_at: string | null;
  timing: StopTiming;
  diff_minutes: number | null;
}

export interface RouteRow {
  id: number;
  code: string;
  status: RouteStatus;
  status_label: string;
  criterion: "time" | "distance";
  depot: string;
  driver: string | null;
  vehicle: string | null;
  departure_at: string;
  finish_at: string;
  started_at: string | null;
  completed_at: string | null;
  driving_minutes: number;
  total_km: number;
  minutes_saved: number | null;
  data_source: string;
  /** El listado (/api/v2/routes/) no trae timing ni progress: se calcula con progressOf. */
  stops: Pick<RouteStopRow, "id" | "status">[];
}

export interface RouteLeg {
  nodes: string[];
  roads?: string[];
  minutes: number;
  km: number;
  band?: string;
}

export interface RerouteRow {
  id: number;
  route_id: number;
  route_code: string;
  incident_id: number | null;
  summary: string;
  current_minutes: number;
  proposed_minutes: number;
  minutes_saved: number;
  status: "pending" | "accepted" | "kept" | "expired";
  status_label: string;
  created_at: string;
  decided_at: string | null;
}

export interface RouteDetail {
  route: Omit<RouteRow, "stops"> & { stops: RouteStopRow[]; progress: Progress };
  legs: RouteLeg[];
  reroutes: RerouteRow[];
  late_tolerance_min: number;
}

export interface Dashboard {
  routes_in_progress: number;
  routes_planned_today: number;
  delayed_stops: number;
  unassigned_orders: number;
  deliveries_today: number;
  late_tolerance_min: number;
}

export interface MonitorRoute {
  id: number;
  code: string;
  status: RouteStatus;
  status_label: string;
  driver: string | null;
  vehicle: string | null;
  departure_at: string;
  finish_at: string;
  started_at: string | null;
  progress: Progress;
  next_stop: { sequence: number; order_code: string; recipient: string; address: string; eta: string } | null;
  delay_minutes: number;
  pending_reroutes: number;
}

export interface IncidentRow {
  id: number;
  kind: string;
  kind_label: string;
  blocked: boolean;
  multiplier: number;
  starts_at: string;
  ends_at: string | null;
  note: string;
  route_code: string | null;
  edges: string[];
}

export interface Monitoring {
  routes: MonitorRoute[];
  incidents: IncidentRow[];
  proposals: RerouteRow[];
  refreshed_at: string;
}

export interface ExperimentResult {
  key: "e1" | "e2" | "e3" | "e5" | "e7";
  title: string;
  file: string;
  rows: number;
  /** Cada experimento trae un resumen distinto; se lee según su clave. */
  summary: Record<string, unknown>;
  updated_at: string;
  data_sources: string[];
  is_real_data: boolean;
}

export interface Reports {
  minutes_saved: { total: number; routes: number; by_route: { code: string; minutes_saved: number }[] };
  punctuality: { delivered: number; on_time: number; pct: number | null; tolerance_min: number };
  failed_by_reason: { reason: string; count: number }[];
  experiments: ExperimentResult[];
}

const REFRESH_MS = 30_000;

export function useRoutes() {
  return useQuery({
    queryKey: ["routes"],
    queryFn: () => api<{ routes: RouteRow[] }>("/api/v2/routes/"),
  });
}

export function useRouteDetail(id: string | undefined) {
  return useQuery({
    queryKey: ["route", id],
    queryFn: () => api<RouteDetail>(`/api/v2/routes/${id}/`),
    enabled: !!id,
    retry: false,
  });
}

export function useDashboard() {
  return useQuery({ queryKey: ["dashboard"], queryFn: () => api<Dashboard>("/api/v2/dashboard/"), refetchInterval: REFRESH_MS });
}

export function useMonitoring() {
  return useQuery({
    queryKey: ["monitoring"],
    queryFn: () => api<Monitoring>("/api/v2/monitoring/"),
    refetchInterval: REFRESH_MS,
  });
}

export function useReports() {
  return useQuery({ queryKey: ["reports"], queryFn: () => api<Reports>("/api/v2/reports/") });
}

export function progressOf(stops: { status: StopStatus }[]): Progress {
  return {
    delivered: stops.filter((s) => s.status === "delivered").length,
    failed: stops.filter((s) => s.status === "failed").length,
    total: stops.length,
  };
}

/** Paradas resueltas (entregadas o fallidas) sobre el total, de 0 a 100. */
export function progressPct(p: Progress): number {
  return p.total === 0 ? 0 : Math.round((100 * (p.delivered + p.failed)) / p.total);
}

/** "edges=estimate;traffic=synthetic" → { edges, traffic } (formato de Route.data_source). */
export function parseDataSource(text: string | undefined): { edges: string; traffic: string } | undefined {
  if (!text) return undefined;
  const pairs = Object.fromEntries(text.split(";").map((part) => part.split("=") as [string, string]));
  return { edges: pairs.edges ?? "desconocido", traffic: pairs.traffic ?? "desconocido" };
}

/** "+12 min" / "−3 min" / "a la hora"; el signo es siempre real − estimado. */
export function formatDiff(minutes: number | null | undefined): string {
  if (minutes == null) return "—";
  const rounded = Math.round(minutes);
  if (rounded === 0) return "a la hora";
  return `${rounded > 0 ? "+" : "−"}${Math.abs(rounded)} min`;
}
