import { RadioIcon } from "lucide-react";
import { Button } from "@/components/ui/button";
import { ErrorNote } from "@/components/ui/misc";
import { formatClock, formatMinutes } from "@/lib/format";
import { formatLiveDiff, liveTone, useLiveCheck } from "@/lib/live";

/** Compara lo que calculó nuestro algoritmo con lo que Google mide ahora en esos mismos tramos. */
export function LiveCheck({ routeId, status }: { routeId: number; status: string }) {
  const check = useLiveCheck();
  const result = check.data;
  if (status === "completed" || status === "canceled") return null;
  const color = result && liveTone(result) === "ok" ? "var(--color-ok)" : "var(--color-warn)";

  return (
    <section aria-label="Tráfico de ahora">
      <h2 className="mb-1 text-sm font-semibold">Tráfico de ahora</h2>
      <p className="mb-3 text-[13px] text-ink-2">
        Google mide los tramos que faltan con el tráfico de este momento. No cambia la ruta, solo avisa.
      </p>
      <Button variant="outline" onClick={() => check.mutate(routeId)} disabled={check.isPending}>
        <RadioIcon /> {check.isPending ? "Consultando…" : "Verificar con el tráfico de ahora"}
      </Button>
      {check.error ? <div className="mt-3"><ErrorNote error={check.error} /></div> : null}
      {result ? (
        <div className="mt-3 border-l-2 pl-3" style={{ borderColor: color }}>
          <p className="text-sm font-medium" style={{ color }}>{result.message}</p>
          <p className="num mt-1 text-[13px] text-ink-3">
            Nuestro cálculo {formatMinutes(result.our_minutes)} · Google ahora {formatMinutes(result.google_minutes)} ({formatLiveDiff(result.diff_minutes)})
          </p>
          <ul className="mt-2 divide-y divide-line border-y border-line">
            {result.stops.map((s) => (
              <li key={s.stop_id ?? "regreso"} className="flex items-baseline justify-between gap-3 py-2 text-[13px]">
                <span className="min-w-0 truncate text-ink-3">{s.label}</span>
                <span className="num shrink-0">
                  {formatClock(s.stored_eta)} → <strong className="font-medium">{formatClock(s.google_eta)}</strong>
                </span>
              </li>
            ))}
          </ul>
          <p className="mt-2 text-xs text-ink-2">
            Consultado a las {formatClock(result.checked_at)}{result.cached ? " (resultado de hace menos de 5 min)" : ""}
            {result.partial ? " · Solo se verificaron los primeros tramos." : ""}
          </p>
        </div>
      ) : null}
    </section>
  );
}
