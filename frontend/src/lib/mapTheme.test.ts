import { describe, expect, it } from "vitest";
import { cascadeDelay, mapStyles } from "./mapTheme";

describe("cascadeDelay", () => {
  it("empieza en 0 y termina en el total", () => {
    expect(cascadeDelay(0, 10, 1)).toBe(0);
    expect(cascadeDelay(9, 10, 1)).toBeCloseTo(1);
  });
  it("no pasa del total ni falla con un solo elemento", () => {
    expect(cascadeDelay(50, 10, 1)).toBeCloseTo(1);
    expect(cascadeDelay(0, 1, 1)).toBe(0);
  });
});

describe("mapStyles", () => {
  it("el oscuro es distinto del claro y mantiene ocultos los puntos de interés", () => {
    const dark = mapStyles("dark");
    expect(dark).not.toEqual(mapStyles("light"));
    expect(dark.some((s) => s.featureType === "poi")).toBe(true);
  });
});
