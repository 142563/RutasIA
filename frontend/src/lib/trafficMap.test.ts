import { describe, expect, it } from "vitest";
import { trafficMapEdges } from "./trafficMap";
import type { TrafficProfile } from "./trafficLevel";

const profile: TrafficProfile = {
  band: "peak_am", day_type: "weekday", calibrated: true,
  data_source: { edges: "estimate", traffic: "synthetic" },
  edges: [{ from: "a", to: "b", multiplier: 1.25 }, { from: "b", to: "a", multiplier: 1.8 }],
};
describe("tráfico dirigido en el mapa", () => {
  it("conserva multiplicadores distintos por sentido sin mutar el perfil", () => {
    expect(trafficMapEdges(profile, "peak_am", "weekday")).toEqual(profile.edges);
    expect(profile.edges[0].multiplier).toBe(1.25);
  });
  it("no presenta ausencia de datos o una franja anterior como tráfico fluido", () => {
    expect(trafficMapEdges(undefined, "peak_am", "weekday")).toBeNull();
    expect(trafficMapEdges({ ...profile, calibrated: false }, "peak_am", "weekday")).toBeNull();
    expect(trafficMapEdges(profile, "night", "weekday")).toBeNull();
    expect(trafficMapEdges(profile, "peak_am", "weekend")).toBeNull();
  });
  it("descarta tramos sin sentido o con multiplicadores inválidos", () => {
    expect(trafficMapEdges({ ...profile, edges: [
      ...profile.edges, { multiplier: 2 }, { from: "a", to: "c", multiplier: 0.9 },
      { from: "a", to: "d", multiplier: NaN },
    ] }, "peak_am", "weekday")).toEqual(profile.edges);
  });
});
