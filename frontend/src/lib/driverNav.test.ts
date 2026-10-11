import { describe, expect, it } from "vitest";
import { formatDistance, geometryPairs, haversineKm, minutesToStop, remainingCodes } from "./driverNav";

describe("driverNav", () => {
  const map = { legs: [{ to_sequence: 1, nodes: ["a", "b"] }, { to_sequence: 2, nodes: ["b", "c", "d"] }, { to_sequence: 3, nodes: ["d", "a"] }] };
  it("une solo los tramos que faltan sin repetir empalmes", () => {
    expect(remainingCodes(map, 1)).toEqual(["a", "b", "c", "d", "a"]);
    expect(remainingCodes(map, 2)).toEqual(["b", "c", "d", "a"]);
    expect(remainingCodes(undefined, 1)).toEqual([]);
  });
  it("pares únicos en el orden de la ruta", () => {
    expect(geometryPairs(["a", "b", "c", "b"])).toEqual([["a", "b"], ["b", "c"], ["c", "b"]]);
  });
  it("distancia y tiempo simples", () => {
    expect(haversineKm({ lat: 14.6, lng: -90.5 }, { lat: 14.6, lng: -90.5 })).toBe(0);
    const stop = { lat: 14.7, lng: -90.5, eta: "2026-01-01T10:00:00Z" };
    expect(minutesToStop({ lat: 14.6, lng: -90.5 }, 35, stop)).toBeGreaterThan(10);
    expect(minutesToStop(null, null, stop, new Date("2026-01-01T09:30:00Z"))).toBe(30);
    expect(formatDistance(0.45)).toBe("500 m");
    expect(formatDistance(12.4)).toBe("12 km");
  });
});
