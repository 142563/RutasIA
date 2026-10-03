/** Piezas del monitoreo en vivo; se muestran en la pantalla Hoy. */
import * as React from "react";
import type { ReactNode } from "react";
import { Link } from "react-router";
import { toast } from "sonner";
import { NodeSearch } from "@/components/NodeSearch";
import { Button } from "@/components/ui/button";
import { Field, Input } from "@/components/ui/field";
import { ErrorNote, Segmented, Spinner, StatusDot } from "@/components/ui/misc";
import { ROUTE_STATUS, type MonitorRoute } from "@/lib/dispatch";
import { formatClock, formatMinutes } from "@/lib/format";
import {
  INCIDENT_KINDS, placesLabel, roadsLabel, savingLabel, timeAgo, useDecideReroute, useReportIncident, useResolveIncident,
  type Incident, type IncidentKind, type Reroute,
} from "@/lib/incidents";
import { useNetwork } from "@/lib/queries";
import type { GraphNode } from "@/lib/types";
import { formatWhen, ProgressBar } from "@/pages/routes/shared";

export function RouteItem({ route }: { route: MonitorRoute }) {
  const late = route.delay_minutes > 0;
  return (
    <li className="grid gap-x-6 gap-y-2 border-b border-line py-4 sm:grid-cols-[minmax(0,1.2fr)_minmax(0,1fr)_minmax(0,1fr)]">
      <div className="min-w-0">
        <Link to={`/rutas/${route.id}`} className="num text-sm font-medium hover:underline">{route.code}</Link>
        <p className="text-[13px] text-ink-3">{route.driver ?? "Sin conductor"}{route.vehicle ? ` · ${route.vehicle}` : ""}</p>
        <StatusDot color={ROUTE_STATUS[route.status].color} className="mt-1">
          {route.status_label} · salida {formatWhen(route.departure_at)}
        </StatusDot>
      </div>
      <ProgressBar progress={route.progress} className="self-center" />
      <div className="text-[13px]">
        {route.next_stop ? (
          <>
            <p className="text-ink-2">Próxima parada</p>
            <p className="truncate font-medium">{route.next_stop.sequence}. {route.next_stop.recipient}</p>
            <p className="num text-ink-3">Estimada {formatClock(route.next_stop.eta)}</p>
          </>
        ) : <p className="text-ink-2">Sin paradas pendientes</p>}
        <p className={late ? "num mt-1 font-medium text-warn" : "num mt-1 text-ink-2"}>
          {late ? `Retraso estimado ${formatMinutes(route.delay_minutes)}` : "Sin retraso"}
        </p>
        {route.pending_reroutes > 0 ? <p className="text-xs text-ink-2">Ruta alternativa por decidir</p> : null}
      </div>
    </li>
  );
}

/** Incidente vigente: qué es, dónde, hace cuánto y quién lo reportó. */
export function IncidentItem({ incident }: { incident: Incident }) {
  const resolve = useResolveIncident();
  const roads = roadsLabel(incident.edges);

  function onResolve() {
    resolve.mutate(incident.id, {
      onSuccess: () => toast.success("Incidente resuelto."),
      onError: (error) => toast.error(error.message),
    });
  }

  return (
    <li className="flex items-start justify-between gap-4 border-b border-line py-3 text-[13px]">
      <div className="min-w-0">
        <p className="flex flex-wrap items-baseline gap-x-2">
          <span className="font-medium">{incident.kind_label}</span>
          {incident.blocked ? <span className="font-medium text-err">Carretera cerrada</span> : null}
        </p>
        <p className="text-ink-3">
          {placesLabel(incident.edges)}{roads ? ` · ${roads}` : ""}
        </p>
        {incident.note ? <p className="text-ink-2">{incident.note}</p> : null}
        <p className="text-xs text-ink-2">
          {timeAgo(incident.starts_at)} · {incident.reported_by ? `reportó ${incident.reported_by}` : "reporte del sistema"}
        </p>
      </div>
      <Button variant="outline" size="sm" className="shrink-0" disabled={resolve.isPending} onClick={onResolve}>
        {resolve.isPending ? "Resolviendo…" : "Resolver"}
      </Button>
    </li>
  );
}

/** Recálculo pendiente: ahorro, ruta y piloto; el despachador también puede decidir. */
export function ProposalItem({ reroute, driver }: { reroute: Reroute; driver?: string | null }) {
  const decide = useDecideReroute();

  function onDecide(decision: "accept" | "keep") {
    decide.mutate(
      { id: reroute.id, decision },
      {
        onSuccess: () => toast.success(decision === "accept" ? "Ruta nueva aplicada." : "Se mantiene la ruta actual."),
        onError: (error) => toast.error(error.message),
      },
    );
  }

  return (
    <li className="flex flex-wrap items-center justify-between gap-x-4 gap-y-2 border-b border-line py-3 text-[13px]">
      <div className="min-w-0">
        <p className="font-medium">{reroute.summary || `Ruta más rápida: ${savingLabel(reroute)}`}</p>
        <p className="text-ink-2">
          <Link to={`/rutas/${reroute.route_id}`} className="num hover:underline">{reroute.route_code}</Link>
          {" · "}{driver ?? "Sin conductor"} · {timeAgo(reroute.created_at)}
        </p>
      </div>
      <div className="flex shrink-0 gap-2">
        <Button size="sm" disabled={decide.isPending} onClick={() => onDecide("accept")}>Aceptar</Button>
        <Button size="sm" variant="outline" disabled={decide.isPending} onClick={() => onDecide("keep")}>Mantener</Button>
      </div>
    </li>
  );
}

/** El despachador reporta un incidente eligiendo el tramo con dos buscadores de lugar. */
export function ReportIncidentForm({ onDone }: { onDone: () => void }) {
  const network = useNetwork();
  const report = useReportIncident();
  const [from, setFrom] = React.useState<GraphNode | null>(null);
  const [to, setTo] = React.useState<GraphNode | null>(null);
  const [kind, setKind] = React.useState<IncidentKind>("traffic");
  const [both, setBoth] = React.useState(true);
  const [note, setNote] = React.useState("");
  const [problem, setProblem] = React.useState<string | null>(null);

  function send() {
    if (!from || !to) return setProblem("Elige el lugar donde empieza y donde termina el tramo.");
    if (from.code === to.code) return setProblem("Elige dos lugares distintos.");
    const linked = (network.data?.edges ?? []).some(
      (e) => (e.from === from.code && e.to === to.code) || (e.from === to.code && e.to === from.code),
    );
    if (!linked) return setProblem("Esos dos lugares no están unidos directamente por carretera. Elige lugares vecinos.");
    setProblem(null);
    report.mutate(
      { kind, note: note.trim(), bothDirections: both, edges: [{ from: from.code, to: to.code }] },
      {
        onSuccess: (data) => {
          toast.success(data.proposals.length > 0
            ? `Incidente reportado. Hay ${data.proposals.length} ruta(s) alternativa(s) por decidir.`
            : "Incidente reportado. Ninguna ruta de hoy se ve afectada.");
          onDone();
        },
        onError: (error) => toast.error(error.message),
      },
    );
  }

  if (network.isPending) return <Spinner label="Cargando lugares…" />;
  if (network.isError) return <ErrorNote error={network.error} />;
  const nodes = network.data.nodes;

  return (
    <div className="flex flex-col gap-4 rounded-xl border border-line bg-surface p-4">
      <div className="grid gap-3 sm:grid-cols-2">
        <Field label="Desde" htmlFor="inc-from"><NodeSearch id="inc-from" nodes={nodes} onSelect={setFrom} placeholder="Ej. Escuintla" /></Field>
        <Field label="Hasta" htmlFor="inc-to"><NodeSearch id="inc-to" nodes={nodes} onSelect={setTo} placeholder="Ej. Palín" /></Field>
      </div>
      <Segmented<IncidentKind> label="Tipo de incidente" value={kind} onChange={setKind}
        options={INCIDENT_KINDS.map((k) => ({ value: k.value, label: k.label }))} />
      <label className="flex items-center gap-2 text-[13px]">
        <input type="checkbox" checked={both} onChange={(e) => setBoth(e.target.checked)} className="size-4 accent-ink" />
        Afecta ambos sentidos
      </label>
      <Field label="Nota (opcional)" htmlFor="inc-note">
        <Input id="inc-note" value={note} maxLength={255} onChange={(e) => setNote(e.target.value)} placeholder="Ej. Camión volcado" />
      </Field>
      {problem ? <p className="text-[13px] text-err" role="alert">{problem}</p> : null}
      <div className="flex gap-2">
        <Button disabled={report.isPending} onClick={send}>{report.isPending ? "Enviando…" : "Reportar incidente"}</Button>
        <Button variant="ghost" disabled={report.isPending} onClick={onDone}>Cancelar</Button>
      </div>
    </div>
  );
}

export function Section({ title, count, children }: { title: string; count: number; children: ReactNode }) {
  return (
    <section>
      <h2 className="flex items-baseline gap-2 border-b border-line pb-2 text-sm font-semibold">
        {title} <span className="num text-xs font-normal text-ink-2">{count}</span>
      </h2>
      {children}
    </section>
  );
}
