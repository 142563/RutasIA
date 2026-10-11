import { describe, expect, it } from "vitest";
import { trafficLevel, type TrafficProfile } from "./trafficLevel";

const profile = (values: number[]): TrafficProfile => ({
  band: "peak_am", day_type: "weekday", calibrated: true,
  edges: values.map((multiplier) => ({ multiplier })), data_source: { edges: "google", traffic: "google" },
});
const level = (p: TrafficProfile | undefined) => trafficLevel(p, "peak_am", "weekday");

describe("trafficLevel", () => {
  it.each([[1, "fluido"], [1.1, "leve"], [1.25, "moderado"], [1.5, "pesado"], [1.75, "muy pesado"]])("clasifica el límite %s", (m, word) => {
    expect(level(profile([Number(m)]))?.word).toBe(word);
  });
  it("usa la mediana impar y par sin modificar los datos", () => {
    const p = profile([3, 1, 1.2]);
    expect(level(p)?.median).toBe(1.2);
    expect(p.edges[0].multiplier).toBe(3);
    expect(level(profile([1, 1.2, 1.3, 3]))?.median).toBe(1.25);
  });
  it("no inventa un nivel sin datos ni con otra franja o día", () => {
    expect(level(undefined)).toBeNull();
    expect(level(profile([]))).toBeNull();
    expect(level({ ...profile([1]), calibrated: false })).toBeNull();
    expect(level({ ...profile([1]), band: "night" })).toBeNull();
    expect(level({ ...profile([1]), day_type: "weekend" })).toBeNull();
    expect(level(profile([NaN, Infinity, 0]))).toBeNull();
  });
  it("identifica datos sintéticos y descarta valores inválidos", () => {
    expect(level({ ...profile([NaN, 1.5, -1]), data_source: { edges: "estimate", traffic: "synthetic" } })).toMatchObject({ median: 1.5, synthetic: true });
  });
});
