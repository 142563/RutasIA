import { describe, expect, it } from "vitest";
import { CONGESTION_STEPS, congestionColor, congestionStep, relativeLuminance } from "./congestion";

describe("escala de congestión", () => {
  it("asigna el tramo según el multiplicador", () => {
    expect(congestionStep(1.0)).toBe(0);
    expect(congestionStep(1.09)).toBe(0);
    expect(congestionStep(1.1)).toBe(1);
    expect(congestionStep(1.6)).toBe(3);
    expect(congestionStep(2.4)).toBe(4);
    expect(congestionColor(1.8)).toBe(CONGESTION_STEPS[4].color);
  });

  it("es secuencial: la luminosidad baja estrictamente de fluido a muy pesado", () => {
    const luminances = CONGESTION_STEPS.map((s) => relativeLuminance(s.color));
    for (let i = 1; i < luminances.length; i++) expect(luminances[i]).toBeLessThan(luminances[i - 1]);
  });

  it("el tramo más oscuro contrasta al menos 3:1 con el fondo blanco", () => {
    const darkest = relativeLuminance(CONGESTION_STEPS[CONGESTION_STEPS.length - 1].color);
    expect((1 + 0.05) / (darkest + 0.05)).toBeGreaterThanOrEqual(3);
  });
});
