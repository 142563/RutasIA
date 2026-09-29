/** Franjas horarias (mismas fronteras que logistics/routing/traffic.py). */

export type Band = "dawn" | "peak_am" | "mid_morning" | "midday" | "afternoon" | "peak_pm" | "night";
export type DayType = "weekday" | "weekend";

export const BANDS: { id: Band; label: string; hours: string; start: number }[] = [
  { id: "dawn", label: "Madrugada", hours: "05:00–07:00", start: 5 },
  { id: "peak_am", label: "Pico mañana", hours: "07:00–09:00", start: 7 },
  { id: "mid_morning", label: "Media mañana", hours: "09:00–12:00", start: 9 },
  { id: "midday", label: "Mediodía", hours: "12:00–14:00", start: 12 },
  { id: "afternoon", label: "Tarde", hours: "14:00–17:00", start: 14 },
  { id: "peak_pm", label: "Pico tarde", hours: "17:00–20:00", start: 17 },
  { id: "night", label: "Noche", hours: "20:00–05:00", start: 20 },
];

/** Hora representativa de cada franja (como REPRESENTATIVE_TIME en el backend). */
export const BAND_TIME: Record<Band, string> = {
  dawn: "06:00",
  peak_am: "08:00",
  mid_morning: "10:30",
  midday: "13:00",
  afternoon: "15:30",
  peak_pm: "18:30",
  night: "23:00",
};

/** Hora y día de la semana en Guatemala (UTC−6, sin horario de verano). */
function guatemalaParts(date: Date): { hour: number; weekday: number } {
  const gt = new Date(date.getTime() - 6 * 60 * 60 * 1000);
  return { hour: gt.getUTCHours(), weekday: gt.getUTCDay() };
}

export function bandFor(date: Date): Band {
  const { hour } = guatemalaParts(date);
  let current: Band = "night";
  for (const band of BANDS) if (hour >= band.start) current = band.id;
  return current;
}

export function dayTypeFor(date: Date): DayType {
  const { weekday } = guatemalaParts(date);
  return weekday === 0 || weekday === 6 ? "weekend" : "weekday";
}

export function bandLabel(band: Band): string {
  return BANDS.find((b) => b.id === band)?.label ?? band;
}
