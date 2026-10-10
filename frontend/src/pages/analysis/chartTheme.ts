/* Estilos compartidos de Recharts para Análisis: todo con tokens para que funcione en claro y oscuro. */
export const AXIS_TICK = { fontSize: 11, fill: "var(--color-ink-2)" } as const;
export const GRID_STROKE = "var(--color-line)";
export const AXIS_LINE = { stroke: "var(--color-line-strong)" } as const;

export const TOOLTIP_STYLE = {
  background: "var(--color-elevated)",
  border: "1px solid var(--color-line)",
  borderRadius: 8,
  boxShadow: "var(--shadow-pop)",
  color: "var(--color-ink)",
  fontSize: 12,
} as const;
export const TOOLTIP_LABEL = { color: "var(--color-ink-2)", marginBottom: 2 } as const;
export const TOOLTIP_ITEM = { color: "var(--color-ink)" } as const;
export const TOOLTIP_CURSOR = { fill: "var(--color-hover)", opacity: 0.6 } as const;
