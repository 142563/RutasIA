/** Conductor · "Reportar" un problema en la carretera (tránsito, accidente, derrumbe, cierre). */
import { CarFrontIcon, MegaphoneIcon, MountainIcon, OctagonXIcon, TriangleAlertIcon } from "lucide-react";
import * as React from "react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Select, Textarea } from "@/components/ui/field";
import { ErrorNote } from "@/components/ui/misc";
import { INCIDENT_KINDS, useIncidents, useReportIncident, type DriverSegment, type IncidentKind } from "@/lib/incidents";
import { cn } from "@/lib/utils";

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
  const [kind, setKind] = React.useState<IncidentKind | null>(null);
  const [note, setNote] = React.useState("");
  const [segmentIndex, setSegmentIndex] = React.useState(0);

  const segments = (incidents.data?.segments ?? []).filter((s) => s.route_id === routeId);
  if (segments.length === 0) return null; // sin tramo pendiente no hay dónde reportar

  const segment = segments[Math.min(segmentIndex, segments.length - 1)];

  function close() {
    setOpen(false);
    setKind(null);
    setNote("");
    setSegmentIndex(0);
  }

  function send() {
    if (!kind) return;
    report.mutate(
      { kind, note: note.trim(), routeId, edges: [{ from: segment.from.code, to: segment.to.code }] },
      {
        onSuccess: () => {
          toast.success("Gracias. Avisamos al despachador.");
          close();
        },
        onError: (error) => toast.error(error.message),
      },
    );
  }

  if (!open) {
    return (
      <Button variant="outline" className="h-12 rounded-xl text-[15px]" onClick={() => setOpen(true)}>
        <MegaphoneIcon /> Reportar un problema
      </Button>
    );
  }

  return (
    <section aria-label="Reportar un problema" className="flex flex-col gap-4 rounded-2xl border border-line bg-bg p-4">
      <h2 className="text-[17px] font-semibold tracking-tight">¿Qué pasa en el camino?</h2>
      <div role="radiogroup" aria-label="Tipo de problema" className="grid grid-cols-2 gap-2.5">
        {INCIDENT_KINDS.map((k) => (
          <button
            key={k.value}
            type="button"
            role="radio"
            aria-checked={kind === k.value}
            onClick={() => setKind(k.value)}
            className={cn(
              "flex min-h-[88px] flex-col items-center justify-center gap-2 rounded-xl border px-2 text-center text-[14px] font-medium [&_svg]:size-7",
              kind === k.value ? "border-ink bg-surface shadow-[0_0_0_1px_var(--color-ink)]" : "border-line-strong bg-surface text-ink-3",
            )}
          >
            {ICONS[k.value]}
            {k.label}
          </button>
        ))}
      </div>

      {segments.length > 1 ? (
        <label className="flex flex-col gap-1.5 text-[13px] text-ink-2">
          ¿En qué tramo?
          <Select className="h-11" value={segmentIndex} onChange={(e) => setSegmentIndex(Number(e.target.value))}>
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
      />
      {report.isError ? <ErrorNote error={report.error} /> : null}
      <div className="grid gap-2.5">
        <Button className="h-12 rounded-xl text-[15px]" disabled={!kind || report.isPending} onClick={send}>
          {report.isPending ? "Enviando…" : "Enviar reporte"}
        </Button>
        <Button variant="ghost" className="h-12 rounded-xl text-[15px]" disabled={report.isPending} onClick={close}>
          Cancelar
        </Button>
      </div>
    </section>
  );
}
