/** Formatos para cifras en la interfaz (siempre en español). */

export function formatMinutes(minutes: number | null | undefined): string {
  if (minutes == null || !Number.isFinite(minutes)) return "—";
  const total = Math.round(minutes);
  const h = Math.floor(total / 60);
  const m = total % 60;
  if (h === 0) return `${m} min`;
  return `${h} h ${String(m).padStart(2, "0")} min`;
}

export function formatKm(km: number | null | undefined): string {
  if (km == null || !Number.isFinite(km)) return "—";
  return `${km.toLocaleString("es-GT", { maximumFractionDigits: km < 10 ? 1 : 0 })} km`;
}

/** "07:30" desde una fecha ISO con zona, mostrada en hora de Guatemala. */
export function formatClock(iso: string | null | undefined): string {
  if (!iso) return "—";
  return new Date(iso).toLocaleTimeString("es-GT", {
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
    timeZone: "America/Guatemala",
  });
}

export function formatDateLong(date: Date): string {
  const text = date.toLocaleDateString("es-GT", {
    weekday: "long",
    day: "numeric",
    month: "long",
    timeZone: "America/Guatemala",
  });
  return text.charAt(0).toUpperCase() + text.slice(1);
}

/** Valor para <input type="datetime-local"> en hora de Guatemala (UTC−6, sin horario de verano). */
export function toLocalInputValue(date: Date): string {
  const gt = new Date(date.getTime() - 6 * 60 * 60 * 1000);
  return gt.toISOString().slice(0, 16);
}
