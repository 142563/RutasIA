import { TriangleAlertIcon } from "lucide-react";
import { isRealData } from "@/lib/queries";
import type { DataSource } from "@/lib/types";

/**
 Aviso de fuente. Con datos estimados o sintéticos (no aptos para la tesis) es una alerta;
 con `alwaysShow` y datos reales queda como una línea discreta con la procedencia.
*/
export function DataSourceNote({ source, alwaysShow }: { source?: DataSource; alwaysShow?: boolean }) {
  if (!source) return null;
  if (isRealData(source)) {
    if (!alwaysShow) return null;
    return (
      <p className="num text-xs text-ink-2">
        Fuente: tramos {source.edges} · tráfico {source.traffic}
      </p>
    );
  }
  return (
    <p className="flex items-start gap-2 rounded-lg border border-warn/25 bg-warn/5 px-3 py-2 text-[13px] text-warn" role="note">
      <TriangleAlertIcon className="mt-0.5 size-4 shrink-0" aria-hidden />
      <span>
        Datos de desarrollo: tramos <b>{source.edges}</b> y tráfico <b>{source.traffic}</b>. Los tiempos no vienen de
        Google todavía; no los uses como resultados.
      </span>
    </p>
  );
}
