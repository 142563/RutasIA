/** Incidentes en la carretera y recálculo de rutas (docs/PLAN.md §8, flujo C). */
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "./api";
import type { DriverRoute } from "./driver";
import type { NodeRef } from "./types";

export type IncidentKind = "traffic" | "accident" | "landslide" | "closure";

/** Tipos que se pueden reportar, con el texto corto que ve la gente. */
export const INCIDENT_KINDS: { value: IncidentKind; label: string }[] = [
  { value: "traffic", label: "Tránsito pesado" },
  { value: "accident", label: "Accidente" },
  { value: "landslide", label: "Derrumbe" },
  { value: "closure", label: "Carretera cerrada" },
];

export interface IncidentEdge {
  id: number;
  road: string;
  km: number;
  from: NodeRef;
  to: NodeRef;
}

export interface Incident {
  id: number;
  kind: IncidentKind;
  kind_label: string;
  blocked: boolean;
  starts_at: string;
  ends_at: string | null;
  note: string;
  route_id: number | null;
  reported_by: string | null;
  edges: IncidentEdge[];
}

export interface Reroute {
  id: number;
  route_id: number;
  route_code: string;
  incident_id: number | null;
  summary: string;
  minutes_saved: number;
  current_blocked: boolean;
  created_at: string;
}

/** Tramo que el conductor está recorriendo (para el botón "Reportar"). */
export interface DriverSegment {
  route_id: number;
  route_code: string;
  road: string;
  from: NodeRef;
  to: NodeRef;
}

export interface IncidentsResponse {
  incidents: Incident[];
  reroutes: Reroute[];
  /** Solo para el conductor. */
  segments?: DriverSegment[];
}

export const INCIDENTS_POLL_MS = 30_000;
const KEY = ["incidents"];

/** Incidentes vigentes y recálculos pendientes. Se sondea cada 30 s si `poll` es true. */
export function useIncidents(poll = true) {
  return useQuery({
    queryKey: KEY,
    queryFn: () => api<IncidentsResponse>("/api/traffic/incidents/"),
    refetchInterval: poll ? INCIDENTS_POLL_MS : false,
    refetchOnWindowFocus: true,
  });
}

function useRefreshAll() {
  const client = useQueryClient();
  return () =>
    Promise.all(
      [KEY, ["monitoring"], ["driver", "today"], ["dashboard"], ["routes"], ["route"]].map((queryKey) => client.invalidateQueries({ queryKey })),
    );
}

export interface ReportInput {
  kind: IncidentKind;
  note?: string;
  routeId?: number;
  bothDirections?: boolean;
  /** Pares de códigos de lugar, en el sentido del recorrido. */
  edges: { from: string; to: string }[];
}

export function useReportIncident() {
  const refresh = useRefreshAll();
  return useMutation({
    mutationFn: (v: ReportInput) =>
      api<{ incident: Incident; proposals: Reroute[] }>("/api/traffic/incidents/", {
        method: "POST",
        body: { kind: v.kind, note: v.note || undefined, route_id: v.routeId, both_directions: v.bothDirections, edges: v.edges },
      }),
    onSuccess: refresh,
  });
}

export function useResolveIncident() {
  const refresh = useRefreshAll();
  return useMutation({
    mutationFn: (id: number) => api<{ incident: Incident }>(`/api/traffic/incidents/${id}/resolve/`, { method: "POST", body: {} }),
    onSuccess: refresh,
  });
}

export function useDecideReroute() {
  const refresh = useRefreshAll();
  return useMutation({
    mutationFn: (v: { id: number; decision: "accept" | "keep" }) =>
      api<{ route: DriverRoute }>(`/api/reroutes/${v.id}/decision/`, { method: "POST", body: { decision: v.decision } }),
    onSuccess: refresh,
  });
}

/** "Escuintla → Palín" (primer y último lugar del tramo). */
export function placesLabel(edges: Pick<IncidentEdge, "from" | "to">[]): string {
  if (edges.length === 0) return "Tramo sin identificar";
  const first = edges[0].from.name;
  const last = edges[edges.length - 1].to.name;
  return first === last ? first : `${first} → ${last}`;
}

/** Carreteras distintas de un incidente: "CA-9 Sur". */
export function roadsLabel(edges: Pick<IncidentEdge, "road">[]): string {
  const roads = [...new Set(edges.map((e) => e.road).filter(Boolean))];
  return roads.join(", ");
}

/** "hace 5 min", "hace 2 h", "hace 3 d". */
export function timeAgo(iso: string, now: Date = new Date()): string {
  const minutes = Math.max(0, Math.round((now.getTime() - new Date(iso).getTime()) / 60_000));
  if (minutes < 1) return "hace un momento";
  if (minutes < 60) return `hace ${minutes} min`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `hace ${hours} h`;
  return `hace ${Math.floor(hours / 24)} d`;
}

/** Título del aviso: "Tránsito pesado en CA-9 Sur" (o el tramo, si no hay carretera). */
export function incidentHeadline(incident: Incident | undefined): string {
  if (!incident) return "Hay un problema en tu camino";
  const where = roadsLabel(incident.edges) || placesLabel(incident.edges);
  return `${incident.kind_label} en ${where}`;
}

/** Texto del ahorro: "−18 min", o "evita el tramo cerrado". */
export function savingLabel(reroute: Pick<Reroute, "minutes_saved" | "current_blocked">): string {
  return reroute.current_blocked ? "evita el tramo cerrado" : `−${Math.max(Math.round(reroute.minutes_saved), 1)} min`;
}
