import { describe, expect, it } from "vitest";
import { joinLegNodes, MAX_WAYPOINTS, sampleWaypoints } from "./roads";

describe("submuestreo de waypoints", () => {
  const seq = (n: number) => Array.from({ length: n }, (_, i) => i);

  it("no toca las rutas cortas", () => {
    expect(sampleWaypoints(seq(10))).toEqual(seq(10));
    expect(sampleWaypoints(seq(MAX_WAYPOINTS + 2))).toHaveLength(MAX_WAYPOINTS + 2);
  });

  it("limita a 25 intermedios y conserva origen y destino en orden", () => {
    const out = sampleWaypoints(seq(120));
    expect(out).toHaveLength(MAX_WAYPOINTS + 2);
    expect(out[0]).toBe(0);
    expect(out[out.length - 1]).toBe(119);
    expect(out).toEqual([...out].sort((a, b) => a - b));
    expect(new Set(out).size).toBe(out.length);
  });

  it("reparte los puntos de forma pareja", () => {
    expect(sampleWaypoints(seq(101), 4)).toEqual([0, 20, 40, 60, 80, 100]);
  });
});

describe("unión de tramos", () => {
  it("no repite el nodo donde empalman los tramos", () => {
    expect(joinLegNodes([{ nodes: ["a", "b", "c"] }, { nodes: ["c", "d"] }, { nodes: ["d", "e"] }])).toEqual(["a", "b", "c", "d", "e"]);
  });
});
