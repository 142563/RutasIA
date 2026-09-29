/** Piezas del monitoreo en vivo; se muestran en la pantalla Hoy. */
import type { ReactNode } from "react";
import { Link } from "react-router";
import { StatusDot } from "@/components/ui/misc";
import { ROUTE_STATUS, type IncidentRow, type MonitorRoute, type RerouteRow } from "@/lib/dispatch";
import { formatClock, formatMinutes } from "@/lib/format";
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
        {route.pending_reroutes > 0 ? <p className="text-xs text-ink-2">{route.pending_reroutes} recálculo(s) pendiente(s)</p> : null}
      </div>
    </li>
  );
}

export function IncidentItem({ incident }: { incident: IncidentRow }) {
  return (
    <li className="border-b border-line py-3 text-[13px]">
      <p className="flex flex-wrap items-baseline gap-x-2">
        <span className="font-medium">{incident.kind_label}</span>
        <span className={incident.blocked ? "font-medium text-err" : "text-warn"}>
          {incident.blocked ? "Bloqueado" : `Penaliza ×${incident.multiplier.toFixed(2)}`}
        </span>
      </p>
      {incident.edges.length > 0 ? <p className="text-ink-3">{incident.edges.join(" · ")}</p> : null}
      {incident.note ? <p className="text-ink-2">{incident.note}</p> : null}
      <p className="num text-xs text-ink-2">
        Desde {formatWhen(incident.starts_at)}{incident.ends_at ? ` hasta ${formatWhen(incident.ends_at)}` : ""}
        {incident.route_code ? ` · reportado en ${incident.route_code}` : ""}
      </p>
    </li>
  );
}

export function ProposalItem({ proposal }: { proposal: RerouteRow }) {
  return (
    <li className="border-b border-line py-3 text-[13px]">
      <p className="font-medium">{proposal.summary || `Ahorra ${formatMinutes(proposal.minutes_saved)}`}</p>
      <p className="num text-ink-2">
        <Link to={`/rutas/${proposal.route_id}`} className="hover:underline">{proposal.route_code}</Link>
        {" · "}{formatMinutes(proposal.current_minutes)} → {formatMinutes(proposal.proposed_minutes)} · {formatWhen(proposal.created_at)}
      </p>
    </li>
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
