/**
 Escala de congestión (docs/PLAN.md §9): secuencial de un solo tono, de claro a
 oscuro según el multiplicador m. Un solo tono con luminosidad decreciente se
 lee también con daltonismo e impreso en gris; nunca verde/rojo.
*/

export const CONGESTION_STEPS: { min: number; color: string; label: string }[] = [
  { min: 1.0, color: "var(--color-congestion-0)", label: "Fluido (×1.0–1.1)" },
  { min: 1.1, color: "var(--color-congestion-1)", label: "Leve (×1.1–1.25)" },
  { min: 1.25, color: "var(--color-congestion-2)", label: "Moderado (×1.25–1.5)" },
  { min: 1.5, color: "var(--color-congestion-3)", label: "Pesado (×1.5–1.75)" },
  { min: 1.75, color: "var(--color-congestion-4)", label: "Muy pesado (×1.75 o más)" },
];

export function congestionStep(multiplier: number): number {
  let index = 0;
  CONGESTION_STEPS.forEach((step, i) => {
    if (multiplier >= step.min) index = i;
  });
  return index;
}

export function congestionColor(multiplier: number): string {
  return CONGESTION_STEPS[congestionStep(multiplier)].color;
}

/** Luminancia relativa WCAG de un color #rrggbb (para verificar la escala). */
export function relativeLuminance(hex: string): number {
  const channel = (i: number) => {
    const c = parseInt(hex.slice(i, i + 2), 16) / 255;
    return c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4;
  };
  return 0.2126 * channel(1) + 0.7152 * channel(3) + 0.0722 * channel(5);
}
