import { describe, expect, it } from "vitest";
import { interpolatePosition } from "./positionMath";

describe("interpolación de GPS", () => {
  const a = { lat: 14.6, lng: -90.5 };
  const b = { lat: 14.8, lng: -90.3 };
  it("conserva extremos y calcula el punto intermedio sin mutar entradas", () => {
    expect(interpolatePosition(a, b, 0).lat).toBe(a.lat);
    expect(interpolatePosition(a, b, 1).lat).toBe(b.lat);
    const middle = interpolatePosition(a, b, 0.5);
    expect(middle.lat).toBeCloseTo(14.7);
    expect(middle.lng).toBeCloseTo(-90.4);
    expect(a).toEqual({ lat: 14.6, lng: -90.5 });
  });
  it("no extrapola cuando el tiempo se sale del intervalo", () => {
    expect(interpolatePosition(a, b, -5).lat).toBe(a.lat);
    expect(interpolatePosition(a, b, 10).lat).toBe(b.lat);
    expect(interpolatePosition(a, b, NaN).lat).toBe(a.lat);
  });
  it("cruza el meridiano por el trayecto corto", () => {
    expect(Math.abs(interpolatePosition({ lat: 0, lng: 179 }, { lat: 0, lng: -179 }, 0.5).lng)).toBe(180);
  });
});
