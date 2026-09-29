import { TriangleAlertIcon } from "lucide-react";
import { isRealData } from "@/lib/queries";
import type { DataSource } from "@/lib/types";

/** Aviso visible cuando el grafo usa datos estimados o sintéticos (no aptos para la tesis). */
export function DataSourceNote({ source }: { source?: DataSource }) {
  if (!source || isRealData(source)) return null;
  return (
    <p className="flex items-start gap-2 rounded-lg border border-warn/25 bg-warn/5 px-3 py-2 text-[13px] text-warn">
      <TriangleAlertIcon className="mt-0.5 size-4 shrink-0" aria-hidden />
      <span>
        Datos de desarrollo: tramos <b>{source.edges}</b> y tráfico <b>{source.traffic}</b>. Los tiempos no vienen de
        Google todavía; no los uses como resultados.
      </span>
    </p>
  );
}
