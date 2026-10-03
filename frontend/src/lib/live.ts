import { useMutation } from "@tanstack/react-query";
import { api } from "./api";

export interface LiveLeg {
  index: number;
  from: string;
  to: string;
  to_return: boolean;
  our_minutes: number;
  google_minutes: number;
  diff_minutes: number;
}

export interface LiveStop {
  stop_id: number | null;
  sequence: number | null;
  label: string;
  stored_eta: string;
  google_eta: string;
  diff_minutes: number;
}

/** Respuesta de POST /api/v2/routes/<id>/live-check/ (solo informa; no cambia la ruta). */
export interface LiveCheck {
  route_id: number;
  checked_at: string;
  our_minutes: number;
  google_minutes: number;
  diff_minutes: number;
  confirmed: boolean;
  message: string;
  legs: LiveLeg[];
  stops: LiveStop[];
  partial: boolean;
  cached: boolean;
}

export function useLiveCheck() {
  return useMutation({
    mutationFn: (routeId: number) => api<LiveCheck>(`/api/v2/routes/${routeId}/live-check/`, { method: "POST", body: {} }),
  });
}

/** Verde si Google confirma la hora (±5 min); ámbar si hay retraso o adelanto. */
export function liveTone(check: Pick<LiveCheck, "confirmed">): "ok" | "warn" {
  return check.confirmed ? "ok" : "warn";
}

/** "+25 min", "−10 min" o "sin cambio" para una diferencia en minutos. */
export function formatLiveDiff(minutes: number): string {
  const rounded = Math.round(minutes);
  if (rounded === 0) return "sin cambio";
  return `${rounded > 0 ? "+" : "−"}${Math.abs(rounded)} min`;
}
