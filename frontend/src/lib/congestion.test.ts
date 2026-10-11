/// <reference types="node" />
import { describe, expect, it } from "vitest";
import { CONGESTION_STEPS, congestionColor, congestionStep, relativeLuminance } from "./congestion";
import { readFileSync } from "node:fs";

const css = readFileSync(new URL("../index.css", import.meta.url), "utf8");
const light = css.split(".dark {")[0];
const dark = css.split(".dark {")[1].split("@layer base")[0];
function palette(theme: string) {
  return CONGESTION_STEPS.map((s) => {
    const token = s.color.slice(4, -1);
    return theme.match(new RegExp(`${token}:\\s*(#[0-9a-f]{6})`))![1];
  });
}

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
    for (const theme of [light, dark]) {
      const luminances = palette(theme).map(relativeLuminance);
      for (let i = 1; i < luminances.length; i++) expect(luminances[i]).toBeLessThan(luminances[i - 1]);
    }
  });

  it("el tramo más oscuro contrasta al menos 3:1 con el fondo blanco", () => {
    const darkest = relativeLuminance(palette(light).at(-1)!);
    expect((1 + 0.05) / (darkest + 0.05)).toBeGreaterThanOrEqual(3);
  });

  it("mantiene contraste de los tramos sobre la superficie oscura", () => {
    const background = relativeLuminance(dark.match(/--color-surface:\s*(#[0-9a-f]{6})/)![1]);
    for (const color of palette(dark)) expect((relativeLuminance(color) + 0.05) / (background + 0.05)).toBeGreaterThanOrEqual(3);
  });
});
