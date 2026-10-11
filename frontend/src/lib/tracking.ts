/** Seguimiento público del pedido (A3, RUT-71): tipos de /api/public/tracking/<token>/ y lógica pura de la página. */
import { formatClock } from "./format";

export interface TrackingStep {
  key: "received" | "scheduled" | "on_the_way" | "delivered" | "failed";
  label: string;
  at: string | null;
  done: boolean;
}

export interface TrackingData {
  code: string;
  status: "pending" | "assigned" | "in_transit" | "delivered" | "failed" | "canceled";
  status_label: string;
  timeline: TrackingStep[];
  window: { from: string; to: string } | null;
  place: { municipality: string | null; region: string | null };
  driver_name: string | null;
  note: string | null;
}

export type StepState = "done" | "current" | "todo";

/** Estado de cada paso: los hechos, el siguiente pendiente como «actual» y el resto por venir. */
export function stepStates(steps: TrackingStep[]): StepState[] {
  const firstTodo = steps.findIndex((s) => !s.done);
  return steps.map((s, i) => (s.done ? "done" : i === firstTodo ? "current" : "todo"));
}

/** Pasos que se muestran: si no se entregó, se oculta el paso final «Entregado» que ya no ocurrirá. */
export function visibleSteps(steps: TrackingStep[]): TrackingStep[] {
  return steps.filter((s) => s.key !== "failed" || s.done);
}

/** «13:15 – 14:15» en hora de Guatemala, o null si no hay ventana. */
export function formatWindow(window: TrackingData["window"]): string | null {
  if (!window) return null;
  return `${formatClock(window.from)} – ${formatClock(window.to)}`;
}

/** «10 de octubre, 14:32» en hora de Guatemala; vacío si el paso aún no ocurre. */
export function formatStepDate(iso: string | null): string {
  if (!iso) return "";
  const date = new Date(iso);
  const day = date.toLocaleDateString("es-GT", { day: "numeric", month: "long", timeZone: "America/Guatemala" });
  return `${day}, ${formatClock(iso)}`;
}

export type Tone = "ok" | "err" | "accent" | "muted";

export function statusTone(status: TrackingData["status"]): Tone {
  if (status === "delivered") return "ok";
  if (status === "failed" || status === "canceled") return "err";
  if (status === "in_transit") return "accent";
  return "muted";
}

/** Frase corta bajo el estado; vacía si no hay nada útil que agregar. */
export function statusHint(data: TrackingData): string {
  if (data.status === "in_transit") return data.driver_name ? `${data.driver_name} va en camino con tu pedido.` : "Tu pedido va en camino.";
  if (data.status === "assigned") return "Ya tiene fecha de entrega.";
  if (data.status === "pending") return "Te avisaremos por correo cuando tenga fecha de entrega.";
  if (data.status === "delivered") return "Tu pedido fue entregado.";
  return data.note ?? "";
}

/** Entregado, no entregado o cancelado ya no cambian: no hace falta seguir consultando. */
export function isFinal(status: TrackingData["status"]): boolean {
  return status === "delivered" || status === "failed" || status === "canceled";
}

export const TRACKING_REFRESH_MS = 60_000;
