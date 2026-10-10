/** Conductor · "Reportar" un problema en la carretera (tránsito, accidente, derrumbe, cierre). */
import { CarFrontIcon, CheckIcon, MegaphoneIcon, MountainIcon, OctagonXIcon, TriangleAlertIcon } from "lucide-react";
import { AnimatePresence, motion } from "motion/react";
import * as React from "react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Select, Textarea } from "@/components/ui/field";
import { ErrorNote } from "@/components/ui/misc";
import { EASE } from "@/components/ui/motion";
import { INCIDENT_KINDS, useIncidents, useReportIncident, type DriverSegment, type IncidentKind } from "@/lib/incidents";
import { cn } from "@/lib/utils";
import { AnimatedCheck } from "./parts";

const ICONS: Record<IncidentKind, React.ReactNode> = {
  traffic: <CarFrontIcon />,
  accident: <TriangleAlertIcon />,
  landslide: <MountainIcon />,
  closure: <OctagonXIcon />,
};

function segmentText(s: DriverSegment) {
  return `${s.from.name} → ${s.to.name}${s.road ? ` (${s.road})` : ""}`;
}

export function ReportIncident({ routeId }: { routeId: number }) {
  const incidents = useIncidents(false);
  const report = useReportIncident();
  const [open, setOpen] = React.useState(false);
  const [sent, setSent] = React.useState(false);
  const [kind, setKind] = React.useState<IncidentKind | null>(null);
  const [note, setNote] = React.useState("");
  const [segmentIndex, setSegmentIndex] = React.useState(0);
  const timer = React.useRef<ReturnType<typeof setTimeout>>(undefined);
  React.useEffect(() => () => clearTimeout(timer.current), []);

  const segments = (incidents.data?.segments ?? []).filter((s) => s.route_id === routeId);
  if (segments.length === 0 && !sent) return null; // sin tramo pendiente no hay dónde reportar

  const segment = segments[Math.min(segmentIndex, Math.max(segments.length - 1, 0))];

  function close() {
    setOpen(false);
    setSent(false);
    setKind(null);
    setNote("");
    setSegmentIndex(0);
  }

  function send() {
    if (!kind || !segment) return;
    report.mutate(
      { kind, note: note.trim(), routeId, edges: [{ from: segment.from.code, to: segment.to.code }] },
      {
        onSuccess: () => {
          toast.success("Gracias. Avisamos al despachador.");
          setSent(true);
          timer.current = setTimeout(close, 1800);
        },
        onError: (error) => toast.error(error.message),
      },
    );
  }

  return (
    <AnimatePresence mode="wait" initial={false}>
      {!open ? (
        <motion.div key="closed" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0, transition: { duration: 0.1 } }}>
          <Button variant="outline" className="h-14 w-full rounded-xl text-base" onClick={() => setOpen(true)}>
            <MegaphoneIcon aria-hidden /> Reportar un problema
          </Button>
        </motion.div>
      ) : sent ? (
        <motion.section
          key="sent"
          role="status"
          initial={{ opacity: 0, scale: 0.97 }}
          animate={{ opacity: 1, scale: 1, transition: { duration: 0.25, ease: EASE } }}
          className="flex flex-col items-center gap-2 rounded-2xl border border-line bg-surface px-4 py-8 text-center shadow-card"
        >
          <AnimatedCheck size={64} />
          <p className="mt-1 text-[17px] font-semibold tracking-tight">Reporte enviado</p>
          <p className="text-[13px] text-ink-2">El despachador ya lo sabe.</p>
        </motion.section>
      ) : (
        <motion.section
          key="open"
          aria-label="Reportar un problema"
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0, transition: { duration: 0.24, ease: EASE } }}
          exit={{ opacity: 0, transition: { duration: 0.1 } }}
          className="flex flex-col gap-4 rounded-2xl border border-line bg-surface p-4 shadow-lift"
        >
          <h2 className="text-[17px] font-semibold tracking-tight">¿Qué pasa en el camino?</h2>
          <div role="radiogroup" aria-label="Tipo de problema" className="grid grid-cols-2 gap-2.5">
            {INCIDENT_KINDS.map((k) => {
              const on = kind === k.value;
              return (
                <button
                  key={k.value}
                  type="button"
                  role="radio"
                  aria-checked={on}
                  onClick={() => setKind(k.value)}
                  className={cn(
                    "relative flex min-h-[96px] flex-col items-center justify-center gap-2 rounded-xl border px-2 text-center text-[15px] font-medium transition-[border-color,background-color,box-shadow,transform] duration-150 active:scale-[0.97] [&_svg]:size-7",
                    on ? "border-ink bg-bg text-ink shadow-[0_0_0_1px_var(--color-ink)]" : "border-line-strong bg-surface text-ink-3 hover:bg-hover",
                  )}
                >
                  {ICONS[k.value]}
                  {k.label}
                  {on ? (
                    <motion.span
                      initial={{ scale: 0 }}
                      animate={{ scale: 1 }}
                      className="absolute right-2 top-2 flex size-5 items-center justify-center rounded-full bg-ink text-on-ink"
                      aria-hidden
                    >
                      <CheckIcon className="!size-3" strokeWidth={3} />
                    </motion.span>
                  ) : null}
                </button>
              );
            })}
          </div>

          {segments.length > 1 ? (
            <label className="flex flex-col gap-1.5 text-[13px] text-ink-2">
              ¿En qué tramo?
              <Select className="h-12 text-base" value={segmentIndex} onChange={(e) => setSegmentIndex(Number(e.target.value))}>
                {segments.map((s, i) => (
                  <option key={`${s.from.code}-${s.to.code}`} value={i}>{segmentText(s)}</option>
                ))}
              </Select>
            </label>
          ) : (
            <p className="text-[13px] text-ink-2">Tramo: {segmentText(segment)}</p>
          )}

          <Textarea
            value={note}
            maxLength={255}
            onChange={(e) => setNote(e.target.value)}
            placeholder="Nota (opcional)"
            aria-label="Nota"
            className="text-base"
          />
          {report.isError ? <ErrorNote error={report.error} /> : null}
          <div className="grid gap-2.5">
            <Button className="h-14 rounded-xl text-base" disabled={!kind || report.isPending} onClick={send}>
              {report.isPending ? "Enviando…" : "Enviar reporte"}
            </Button>
            <Button variant="ghost" className="h-12 rounded-xl text-[15px]" disabled={report.isPending} onClick={close}>
              Cancelar
            </Button>
          </div>
        </motion.section>
      )}
    </AnimatePresence>
  );
}
