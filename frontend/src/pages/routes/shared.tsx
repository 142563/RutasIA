import { formatClock } from "@/lib/format";
import { progressPct, type Progress } from "@/lib/dispatch";

/** "Hoy 07:30" o "12 oct 07:30", en hora de Guatemala. */
export function formatWhen(iso: string | null | undefined): string {
  if (!iso) return "—";
  const date = new Date(iso);
  const sameDay = date.toDateString() === new Date().toDateString();
  if (sameDay) return `Hoy ${formatClock(iso)}`;
  const day = date.toLocaleDateString("es-GT", { day: "numeric", month: "short", timeZone: "America/Guatemala" });
  return `${day} ${formatClock(iso)}`;
}

/** Barra fina de avance: negro para lo resuelto (el color queda para los estados). */
export function ProgressBar({ progress, className }: { progress: Progress; className?: string }) {
  const pct = progressPct(progress);
  const resolved = progress.delivered + progress.failed;
  return (
    <div className={className}>
      <div
        className="h-1 w-full overflow-hidden rounded-full bg-line"
        role="progressbar"
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={pct}
        aria-label="Avance de la ruta"
      >
        <div className="h-full rounded-full bg-ink" style={{ width: `${pct}%` }} />
      </div>
      <span className="num mt-1 block text-xs text-ink-2">
        {resolved}/{progress.total} paradas
        {progress.failed > 0 ? <span className="text-err"> · {progress.failed} no entregadas</span> : null}
      </span>
    </div>
  );
}
