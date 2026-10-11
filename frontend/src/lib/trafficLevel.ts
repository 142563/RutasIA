import { congestionStep } from "./congestion";
import type { Band, DayType } from "./traffic";
import type { DataSource } from "./types";

export interface TrafficProfile {
  band: Band;
  day_type: DayType;
  calibrated: boolean;
  edges: { from?: string; to?: string; multiplier: number }[];
  data_source: DataSource;
}

const LEVELS = ["fluido", "leve", "moderado", "pesado", "muy pesado"];

/** La mediana evita que unos pocos tramos extremos dominen el resumen nacional. */
export function trafficLevel(profile: TrafficProfile | undefined, band: Band, day: DayType) {
  if (!profile?.calibrated || profile.band !== band || profile.day_type !== day) return null;
  const values = profile.edges.map((edge) => edge.multiplier).filter((m) => Number.isFinite(m) && m >= 1).sort((a, b) => a - b);
  if (!values.length) return null;
  const middle = Math.floor(values.length / 2);
  const median = values.length % 2 ? values[middle] : (values[middle - 1] + values[middle]) / 2;
  const step = congestionStep(median);
  return { word: LEVELS[step], median, step, synthetic: profile.data_source.traffic.includes("synthetic") };
}
