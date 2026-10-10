/** Piezas del monitoreo en vivo; se muestran en la pantalla Hoy. */
import { ChevronRightIcon, RouteIcon } from "lucide-react";
import { AnimatePresence, motion } from "motion/react";
import * as React from "react";
import type { ReactNode } from "react";
import { Link } from "react-router";
import { toast } from "sonner";
import { NodeSearch } from "@/components/NodeSearch";
import { Button } from "@/components/ui/button";
import { Field, Input } from "@/components/ui/field";
import { ErrorNote, Segmented, Spinner } from "@/components/ui/misc";
import { EASE, Skeleton, StaggerItem } from "@/components/ui/motion";
import { progressPct, type MonitorRoute } from "@/lib/dispatch";
import { formatClock, formatMinutes } from "@/lib/format";
import {
  INCIDENT_KINDS, placesLabel, roadsLabel, savingLabel, timeAgo, useDecideReroute, useReportIncident, useResolveIncident,
  type Incident, type IncidentKind, type Reroute,
} from "@/lib/incidents";
import { useNetwork } from "@/lib/queries";
import type { GraphNode } from "@/lib/types";
import { cn } from "@/lib/utils";
import { formatWhen } from "@/pages/routes/shared";

/** Color de estado con tokens (la tabla de lib usa hex fijos; aquí respetamos el modo oscuro). */
const STATUS_TOKEN: Record<MonitorRoute["status"], string> = {
  planned: "var(--color-accent)",
  in_progress: "var(--color-delivery)",
  completed: "var(--color-ok)",
  canceled: "var(--color-ink-2)",
};

/** Barra de avance que crece con transform (no con width) y entra animada. */
export function LiveProgress({ progress, running }: { progress: MonitorRoute["progress"]; running?: boolean }) {
  const pct = progressPct(progress);
  const resolved = progress.delivered + progress.failed;
  return (
    <div className="min-w-0">
      <div
        className="h-1.5 w-full overflow-hidden rounded-full bg-line"
        role="progressbar" aria-valuemin={0} aria-valuemax={100} aria-valuenow={pct} aria-label="Avance de la ruta"
      >
        <motion.div
          className={cn("h-full origin-left rounded-full", running ? "bg-delivery" : "bg-ink")}
          initial={{ scaleX: 0 }} animate={{ scaleX: pct / 100 }} transition={{ duration: 0.7, ease: EASE }}
        />
      </div>
      <p className="num mt-1 flex items-baseline justify-between text-xs text-ink-2">
        <span>{resolved}/{progress.total} paradas</span>
        <span>{pct}%</span>
      </p>
      {progress.failed > 0 ? <p className="text-xs text-err">{progress.failed} no entregadas</p> : null}
    </div>
  );
}

/** Fila de ruta: compacta; al pasar el mouse se resalta y la flecha invita a abrir el detalle. */
export function RouteItem({ route }: { route: MonitorRoute }) {
  const late = route.delay_minutes > 0;
  const running = route.status === "in_progress";
  return (
    <StaggerItem as="li" className="group relative border-b border-line last:border-b-0">
      <div className="-mx-3 grid items-center gap-x-5 gap-y-2 rounded-lg px-3 py-3 transition-colors group-hover:bg-hover group-focus-within:bg-hover sm:grid-cols-[minmax(0,1.1fr)_minmax(0,1fr)_minmax(0,1.1fr)_auto]">
        <div className="min-w-0">
          <Link to={`/rutas/${route.id}`} className="num text-sm font-medium after:absolute after:inset-0 hover:underline focus-visible:rounded">
            {route.code}
          </Link>
          <p className="truncate text-[13px] text-ink-3">{route.driver ?? "Sin conductor"}{route.vehicle ? ` · ${route.vehicle}` : ""}</p>
          <span className="mt-0.5 inline-flex items-center gap-2 text-xs text-ink-2">
            <span className={cn("size-1.5 shrink-0 rounded-full", running && "live-dot")}
              style={{ background: STATUS_TOKEN[route.status] }} aria-hidden />
            {route.status_label} · salida {formatWhen(route.departure_at)}
          </span>
        </div>
        <LiveProgress progress={route.progress} running={running} />
        <div className="min-w-0 text-[13px]">
          {route.next_stop ? (
            <>
              <p className="text-xs text-ink-2">Próxima parada</p>
              <p className="truncate font-medium">{route.next_stop.sequence}. {route.next_stop.recipient}</p>
              <p className="num text-xs text-ink-3">Estimada {formatClock(route.next_stop.eta)}</p>
            </>
          ) : <p className="text-ink-2">Sin paradas pendientes</p>}
          {route.pending_reroutes > 0 ? <p className="text-xs text-ink-2">Ruta alternativa por decidir</p> : null}
        </div>
        <div className="flex items-center justify-between gap-2 sm:flex-col sm:items-end sm:justify-center">
          <span className={cn("num text-xs", late ? "rounded-md bg-warn/10 px-2 py-0.5 font-medium text-warn" : "text-ink-2")}>
            {late ? `Retraso ${formatMinutes(route.delay_minutes)}` : "Sin retraso"}
          </span>
          <ChevronRightIcon className="size-4 text-ink-2 transition-transform group-hover:translate-x-0.5 group-hover:text-ink" aria-hidden />
        </div>
      </div>
    </StaggerItem>
  );
}

/** Entrada y salida de los elementos que aparecen o se resuelven (recálculos, incidentes). */
const presence = {
  initial: { opacity: 0, y: 6 },
  animate: { opacity: 1, y: 0, transition: { duration: 0.26, ease: EASE } },
  exit: { opacity: 0, x: 16, transition: { duration: 0.2, ease: EASE } },
};

/** Lista con entrada/salida animada de sus elementos. */
export function PresenceList({ children }: { children: ReactNode }) {
  return (
    <ul>
      <AnimatePresence initial={false} mode="popLayout">{children}</AnimatePresence>
    </ul>
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
    <motion.li layout="position" {...presence} className="border-b border-line last:border-b-0">
      <div className="-mx-3 flex items-start justify-between gap-4 rounded-lg px-3 py-3 text-[13px] transition-colors hover:bg-hover">
        <div className="flex min-w-0 gap-3">
          <span className={cn("mt-1.5 size-2 shrink-0 rounded-full", incident.blocked ? "bg-err" : "bg-warn")} aria-hidden />
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
        </div>
        <Button variant="outline" size="sm" className="shrink-0" disabled={resolve.isPending} onClick={onResolve}>
          {resolve.isPending ? "Resolviendo…" : "Resolver"}
        </Button>
      </div>
    </motion.li>
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
    <motion.li layout="position" {...presence} className="border-b border-line last:border-b-0">
      <div className="-mx-3 flex flex-wrap items-center justify-between gap-x-4 gap-y-2 rounded-lg px-3 py-3 text-[13px] transition-colors hover:bg-hover">
        <div className="flex min-w-0 gap-3">
          <RouteIcon className="mt-0.5 size-4 shrink-0 text-accent" aria-hidden />
          <div className="min-w-0">
            <p className="font-medium">{reroute.summary || `Ruta más rápida: ${savingLabel(reroute)}`}</p>
            <p className="text-ink-2">
              <Link to={`/rutas/${reroute.route_id}`} className="num hover:underline">{reroute.route_code}</Link>
              {" · "}{driver ?? "Sin conductor"} · {timeAgo(reroute.created_at)}
            </p>
          </div>
        </div>
        <div className="flex shrink-0 gap-2">
          <Button size="sm" disabled={decide.isPending} onClick={() => onDecide("accept")}>Aceptar</Button>
          <Button size="sm" variant="outline" disabled={decide.isPending} onClick={() => onDecide("keep")}>Mantener</Button>
        </div>
      </div>
    </motion.li>
  );
}

/** Marcador de carga con la forma de una fila de ruta (evita saltos al llegar los datos). */
export function RouteRowSkeleton() {
  return (
    <div className="grid gap-x-5 gap-y-2 border-b border-line py-3 last:border-b-0 sm:grid-cols-[minmax(0,1.1fr)_minmax(0,1fr)_minmax(0,1.1fr)_auto]" aria-hidden>
      <div className="space-y-2"><Skeleton className="h-4 w-24" /><Skeleton className="h-3 w-36" /><Skeleton className="h-3 w-28" /></div>
      <div className="space-y-2 self-center"><Skeleton className="h-1.5 w-full" /><Skeleton className="h-3 w-20" /></div>
      <div className="space-y-2"><Skeleton className="h-3 w-20" /><Skeleton className="h-4 w-32" /></div>
      <Skeleton className="h-5 w-16 self-center" />
    </div>
  );
}

/** Marcador de carga para filas simples (recálculos, incidentes). */
export function RowSkeleton() {
  return (
    <div className="flex items-center justify-between gap-4 border-b border-line py-3" aria-hidden>
      <div className="space-y-2"><Skeleton className="h-4 w-56" /><Skeleton className="h-3 w-40" /></div>
      <Skeleton className="h-8 w-20" />
    </div>
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
    <div className="flex flex-col gap-4 rounded-xl border border-line bg-surface p-4 shadow-card">
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
      <AnimatePresence initial={false}>
        {problem ? (
          <motion.p key="problem" role="alert" className="text-[13px] text-err"
            initial={{ opacity: 0, height: 0 }} animate={{ opacity: 1, height: "auto" }} exit={{ opacity: 0, height: 0 }}>
            {problem}
          </motion.p>
        ) : null}
      </AnimatePresence>
      <div className="flex gap-2">
        <Button disabled={report.isPending} onClick={send}>{report.isPending ? "Enviando…" : "Reportar incidente"}</Button>
        <Button variant="ghost" disabled={report.isPending} onClick={onDone}>Cancelar</Button>
      </div>
    </div>
  );
}

/** Bloque con título y conteo (rutas de hoy). */
export function Section({ title, count, children, action }: { title: string; count?: number; children: ReactNode; action?: ReactNode }) {
  return (
    <section>
      <div className="flex items-center justify-between gap-2 border-b border-line pb-2">
        <h2 className="flex items-baseline gap-2 text-sm font-semibold">
          {title}
          {count !== undefined ? <span className="num text-xs font-normal text-ink-2">{count}</span> : null}
        </h2>
        {action}
      </div>
      {children}
    </section>
  );
}
