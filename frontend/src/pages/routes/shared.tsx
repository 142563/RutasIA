import { motion } from "motion/react";
import { EASE } from "@/components/ui/motion";
import { formatClock } from "@/lib/format";
import { progressPct, type Progress } from "@/lib/dispatch";
import { cn } from "@/lib/utils";

/** "Hoy 07:30" o "12 oct 07:30", en hora de Guatemala. */
export function formatWhen(iso: string | null | undefined): string {
  if (!iso) return "—";
  const date = new Date(iso);
  const sameDay = date.toDateString() === new Date().toDateString();
  if (sameDay) return `Hoy ${formatClock(iso)}`;
  const day = date.toLocaleDateString("es-GT", { day: "numeric", month: "short", timeZone: "America/Guatemala" });
  return `${day} ${formatClock(iso)}`;
}

/**
 Barra fina de avance: negro para lo resuelto (el color queda para los estados).
 Crece con scaleX (no anima el ancho, así no fuerza layout). `compact` oculta el texto.
*/
export function ProgressBar({ progress, className, compact }: { progress: Progress; className?: string; compact?: boolean }) {
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
        <motion.div
          className="h-full w-full origin-left rounded-full bg-ink"
          initial={{ scaleX: 0 }}
          animate={{ scaleX: pct / 100 }}
          transition={{ duration: 0.7, ease: EASE }}
        />
      </div>
      <span className={cn("num mt-1 block text-xs text-ink-2", compact && "sr-only")}>
        {resolved}/{progress.total} paradas
        {progress.failed > 0 ? <span className="text-err"> · {progress.failed} no entregadas</span> : null}
      </span>
    </div>
  );
}
