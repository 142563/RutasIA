import { describe, expect, it } from "vitest";
import { geometryPairsFor, mergeTrafficPairs, pairsWithGeometry, pairTitle, toggleLayer, trafficMapEdges } from "./trafficMap";
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

describe("capa de tráfico sobre carretera", () => {
  const pairs = mergeTrafficPairs(trafficMapEdges(profile, "peak_am", "weekday"));
  it("combina los sentidos en un trazo con el peor multiplicador", () => {
    expect(pairs).toHaveLength(1);
    expect(pairs[0]).toMatchObject({ a: "a", b: "b", multiplier: 1.8, ab: 1.25, ba: 1.8 });
    expect(pairTitle(pairs[0], (c) => c.toUpperCase())).toBe("A → B: ×1.25 · B → A: ×1.8");
    expect(geometryPairsFor(pairs)).toEqual([["a", "b"], ["b", "a"]]);
  });
  it("título simple si los sentidos coinciden", () => {
    const same = mergeTrafficPairs([{ from: "a", to: "b", multiplier: 1.5 }, { from: "b", to: "a", multiplier: 1.5 }]);
    expect(pairTitle(same[0], (c) => c)).toBe("a ↔ b: ×1.5");
  });
  it("solo dibuja pares con geometría y usa la inversa si falta un sentido", () => {
    const line = "_p~iF~ps|U_ulLnnqC";
    expect(pairsWithGeometry(pairs, [])).toEqual([]);
    expect(pairsWithGeometry(pairs, [{ from: "a", to: "b", polyline: line }])[0].points).toHaveLength(2);
    const back = pairsWithGeometry(pairs, [{ from: "b", to: "a", polyline: line }])[0].points;
    expect(back[0].lat).toBeCloseTo(40.7, 1);
    expect(pairsWithGeometry(pairs, [{ from: "a", to: "b", polyline: "!" }])).toEqual([]);
  });
  it("los interruptores de Google y nuestro tráfico son excluyentes", () => {
    expect(toggleLayer({ google: false, ours: true }, "google")).toEqual({ google: true, ours: false });
    expect(toggleLayer({ google: true, ours: false }, "ours")).toEqual({ google: false, ours: true });
    expect(toggleLayer({ google: false, ours: true }, "ours")).toEqual({ google: false, ours: false });
  });
});
