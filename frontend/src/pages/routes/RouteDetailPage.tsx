import { ArrowLeftIcon } from "lucide-react";
import * as React from "react";
import { Link, useParams } from "react-router";
import { NetworkMap, type MapMarker } from "@/components/map/NetworkMap";
import { DataSourceNote } from "@/components/DataSourceNote";
import { ErrorNote, Metric, PageHeader, Spinner, StatusDot } from "@/components/ui/misc";
import {
  formatDiff, parseDataSource, ROUTE_STATUS, TIMING, useRouteDetail, type RouteDetail, type RouteStopRow,
} from "@/lib/dispatch";
import { joinLegNodes } from "@/lib/roads";
import { useNetwork } from "@/lib/queries";
import { formatClock, formatKm, formatMinutes } from "@/lib/format";
import { AssignmentSection } from "./AssignmentSection";
import { LiveCheck } from "./LiveCheck";
import { formatWhen, ProgressBar } from "./shared";

function StopItem({ stop, last }: { stop: RouteStopRow; last: boolean }) {
  const timing = TIMING[stop.timing];
  return (
    <li className="relative flex gap-4 pb-6 last:pb-0">
      {!last ? <span className="absolute left-[5px] top-4 h-full w-px bg-line-strong" aria-hidden /> : null}
      <span className="relative mt-1.5 size-[11px] shrink-0 rounded-full ring-4 ring-surface" style={{ background: timing.color }} aria-hidden />
      <div className="grid min-w-0 flex-1 gap-x-6 gap-y-1 sm:grid-cols-[minmax(0,1fr)_auto]">
        <div className="min-w-0">
          <p className="text-sm font-medium">
            <span className="num text-ink-2">{stop.sequence}.</span> {stop.recipient}
            <span className="num ml-2 text-xs font-normal text-ink-2">{stop.order_code}</span>
          </p>
          <p className="truncate text-[13px] text-ink-3">{stop.address}</p>
          {stop.status === "failed" ? (
            <p className="text-[13px] text-err">No entregada{stop.reason ? `: ${stop.reason}` : ""}</p>
          ) : null}
        </div>
        <div className="flex flex-col gap-0.5 sm:items-end">
          <StatusDot color={timing.color}>{timing.label}</StatusDot>
          <p className="num text-[13px] text-ink-3">
            Estimada {formatClock(stop.eta)}
            {stop.delivered_at ? <> · Real {formatClock(stop.delivered_at)} ({formatDiff(stop.diff_minutes)})</> : null}
          </p>
        </div>
      </div>
    </li>
  );
}

/** Mapa de la ruta: el camino lo decidió nuestro A*; Google solo dibuja la carretera entre esos nodos. */
function RouteMap({ detail }: { detail: RouteDetail }) {
  const network = useNetwork();
  const codes = React.useMemo(() => joinLegNodes(detail.legs), [detail.legs]);
  if (codes.length < 2) return null;
  if (!network.data) return <div className="p-6"><Spinner label="Cargando mapa…" /></div>;
  const byCode = new Map(network.data.nodes.map((n) => [n.code, n]));
  const markers: MapMarker[] = [];
  detail.route.stops.forEach((s) => {
    const node = s.node ? byCode.get(s.node.code) : undefined;
    if (node) markers.push({ id: `s${s.id}`, kind: "stop", lat: node.lat, lng: node.lng, label: String(s.sequence) });
  });
  const fitTo = codes.map((c) => byCode.get(c)).filter((n): n is NonNullable<typeof n> => !!n).map((n) => ({ lat: n.lat, lng: n.lng }));
  return (
    <section aria-label="Mapa de la ruta">
      <div className="overflow-hidden rounded-xl border border-line bg-surface p-2">
        <NetworkMap nodes={network.data.nodes} edges={network.data.edges} labels="none" width={720} height={380}
          paths={[{ codes, color: "#2f4bd8", width: 4.5, followRoads: true }]} markers={markers} fitTo={fitTo}
          ariaLabel="Mapa de la ruta con sus paradas" />
      </div>
    </section>
  );
}

function Timeline({ detail }: { detail: RouteDetail }) {
  const { route } = detail;
  return (
    <section aria-label="Línea de tiempo">
      <h2 className="mb-1 text-sm font-semibold">Paradas</h2>
      <p className="mb-5 text-[13px] text-ink-2">
        Hora estimada frente a la real. Se marca retraso si la entrega pasa {detail.late_tolerance_min} min de la estimada.
      </p>
      {route.stops.length === 0 ? (
        <p className="text-sm text-ink-2">Esta ruta no tiene paradas.</p>
      ) : (
        <ol>{route.stops.map((s, i) => <StopItem key={s.id} stop={s} last={i === route.stops.length - 1} />)}</ol>
      )}
    </section>
  );
}

export function RouteDetailPage() {
  const { routeId } = useParams();
  const query = useRouteDetail(routeId);
  const detail = query.data;
  const route = detail?.route;

  return (
    <div>
      <PageHeader
        title={route?.code ?? "Detalle de ruta"}
        subtitle={route ? <>{route.depot} · {formatWhen(route.departure_at)}</> : undefined}
        actions={<Link to="/rutas" className="inline-flex items-center gap-1.5 text-[13px] text-ink-2 hover:text-ink"><ArrowLeftIcon className="size-4" /> Rutas</Link>}
      />
      {query.isPending ? <div className="p-8"><Spinner /></div> : null}
      {query.error ? <div className="p-6 lg:px-8"><ErrorNote error={query.error} /></div> : null}
      {detail && route ? (
        <div className="flex flex-col gap-8 px-6 py-6 lg:px-8">
          <div className="grid grid-cols-2 gap-6 border-b border-line pb-6 sm:grid-cols-4">
            <Metric label="Estado" value={<StatusDot color={ROUTE_STATUS[route.status].color} className="text-base text-ink">{route.status_label}</StatusDot>}
              hint={route.driver ? `${route.driver}${route.vehicle ? ` · ${route.vehicle}` : ""}` : "Sin piloto"} />
            <Metric label="Tiempo de manejo" value={formatMinutes(route.driving_minutes)} hint={`Termina ${formatClock(route.finish_at)}`} />
            <Metric label="Distancia" value={formatKm(route.total_km)} />
            <Metric label="Ahorro vs. la más corta" value={route.minutes_saved != null ? formatMinutes(route.minutes_saved) : "—"}
              hint="Con el mismo tráfico" />
          </div>
          <ProgressBar progress={route.progress} className="max-w-md" />
          <DataSourceNote source={parseDataSource(route.data_source)} />

          <RouteMap detail={detail} />

          <div className="grid gap-10 lg:grid-cols-[minmax(0,1fr)_minmax(0,360px)]">
            <Timeline detail={detail} />
            <div className="flex flex-col gap-8">
              <AssignmentSection route={route} />
              <LiveCheck routeId={route.id} status={route.status} />
              <section aria-label="Tramos">
                <h2 className="mb-3 text-sm font-semibold">Tramos</h2>
                {detail.legs.length === 0 ? <p className="text-sm text-ink-2">Sin tramos guardados.</p> : (
                  <ol className="divide-y divide-line border-y border-line">
                    {detail.legs.map((leg, i) => (
                      <li key={i} className="flex items-baseline justify-between gap-3 py-2.5 text-[13px]">
                        <span className="min-w-0 truncate text-ink-3">
                          <span className="num text-ink-2">{i + 1}.</span> {leg.nodes[0]} → {leg.nodes[leg.nodes.length - 1]}
                          {leg.roads?.length ? <span className="text-ink-2"> · {leg.roads.join(", ")}</span> : null}
                        </span>
                        <span className="num shrink-0">{formatMinutes(leg.minutes)} · {formatKm(leg.km)}</span>
                      </li>
                    ))}
                  </ol>
                )}
              </section>
              <section aria-label="Recálculos">
                <h2 className="mb-3 text-sm font-semibold">Recálculos propuestos</h2>
                {detail.reroutes.length === 0 ? <p className="text-sm text-ink-2">Sin recálculos en esta ruta.</p> : (
                  <ul className="divide-y divide-line border-y border-line">
                    {detail.reroutes.map((p) => (
                      <li key={p.id} className="py-2.5 text-[13px]">
                        <p className="font-medium">{p.summary || `Ahorra ${formatMinutes(p.minutes_saved)}`}</p>
                        <p className="num text-ink-2">
                          {formatMinutes(p.current_minutes)} → {formatMinutes(p.proposed_minutes)} · {p.status_label} · {formatWhen(p.created_at)}
                        </p>
                      </li>
                    ))}
                  </ul>
                )}
              </section>
            </div>
          </div>
        </div>
      ) : null}
    </div>
  );
}
