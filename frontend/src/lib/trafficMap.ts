import type { Band, DayType } from "./traffic";
import type { TrafficProfile } from "./trafficLevel";

/** Solo perfiles vigentes y calibrados; conserva ambos sentidos como tramos distintos. */
export function trafficMapEdges(profile: TrafficProfile | undefined, band: Band, day: DayType) {
  if (!profile?.calibrated || profile.band !== band || profile.day_type !== day) return null;
  return profile.edges.flatMap((edge) =>
    edge.from && edge.to && Number.isFinite(edge.multiplier) && edge.multiplier >= 1
      ? [{ from: edge.from, to: edge.to, multiplier: edge.multiplier }] : []);
}
