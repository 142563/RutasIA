/**
 * Aviso de ruta alternativa (Aceptar / Mantener).
 *
 * Espacio reservado para la ola 2 (incidentes y recálculo, docs/PLAN.md §8 flujo C):
 * cuando exista una propuesta, se recibirá aquí y mostrará el ahorro estimado con
 * los botones "Aceptar" y "Mantener". Por ahora no renderiza nada ni llama a la API.
 */
export interface AlternativeRouteProposal {
  id: number;
  minutes_saved: number;
  reason: string;
}

export function AlternativeRouteNotice({ proposal: _proposal }: { proposal?: AlternativeRouteProposal | null }) {
  return null;
}
