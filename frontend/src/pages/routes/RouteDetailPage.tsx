import { CheckIcon, ChevronRightIcon, XIcon } from "lucide-react";
import * as React from "react";
import { Link, useParams } from "react-router";
import { NetworkMap, type MapMarker } from "@/components/map/NetworkMap";
import { DataSourceNote } from "@/components/DataSourceNote";
import { AnimatedNumber, Skeleton, Stagger, StaggerItem } from "@/components/ui/motion";
import { ErrorNote, StatusDot } from "@/components/ui/misc";
import {
  formatDiff, parseDataSource, ROUTE_STATUS, TIMING, useRouteDetail, type RouteDetail, type RouteStopRow,
} from "@/lib/dispatch";
import { joinLegNodes } from "@/lib/roads";
import { useNetwork } from "@/lib/queries";
import { formatClock, formatKm, formatMinutes } from "@/lib/format";
import { cn } from "@/lib/utils";
import { AssignmentSection } from "./AssignmentSection";
import { LiveCheck } from "./LiveCheck";
import { formatWhen, ProgressBar } from "./shared";

/** Punto de la línea de tiempo según el estado real de la parada. */
function StopMarker({ stop, current }: { stop: RouteStopRow; current: boolean }) {
  if (stop.status === "delivered") {
    return <span className="grid size-6 place-items-center rounded-full bg-ink text-on-ink"><CheckIcon className="size-3.5" aria-hidden /></span>;
  }
  if (stop.status === "failed") {
    return <span className="grid size-6 place-items-center rounded-full border border-err bg-surface text-err"><XIcon className="size-3.5" aria-hidden /></span>;
  }
  if (current) {
    return (
      <span className="relative grid size-6 place-items-center">
        <span className="live-dot size-3 rounded-full bg-accent" aria-hidden />
      </span>
    );
  }
  return <span className="num grid size-6 place-items-center rounded-full border border-line-strong bg-surface text-[11px] text-ink-2">{stop.sequence}</span>;
}

function StopItem({ stop, last, current }: { stop: RouteStopRow; last: boolean; current: boolean }) {
  const timing = TIMING[stop.timing];
  const done = stop.status !== "pending";
  return (
    <StaggerItem as="li" className="relative flex gap-3">
      {/* Conector: lleno (negro) tras una parada resuelta, tenue si falta camino */}
      {!last ? (
        <span className={cn("absolute left-3 top-6 -ml-px h-[calc(100%-1.5rem)] w-0.5", done ? "bg-ink/70" : "bg-line-strong")} aria-hidden />
      ) : null}
      <div className="relative z-10 shrink-0 pt-3"><StopMarker stop={stop} current={current} /></div>
      <div
        className={cn(
          "mb-1 min-w-0 flex-1 rounded-lg px-3 py-3 transition-colors",
          current ? "bg-accent-soft ring-1 ring-accent/30" : "hover:bg-hover/60",
          done && !current && "opacity-65 hover:opacity-100",
        )}
        aria-current={current ? "step" : undefined}
      >
        <div className="flex items-baseline justify-between gap-3">
          <p className="min-w-0 truncate text-sm font-medium">
            {stop.recipient}
            <span className="num ml-2 text-xs font-normal text-ink-2">{stop.order_code}</span>
          </p>
          <span className="num shrink-0 text-[13px]">{formatClock(stop.delivered_at ?? stop.eta)}</span>
        </div>
        <p className="truncate text-[13px] text-ink-3">{stop.address}</p>
        <div className="mt-1 flex flex-wrap items-center justify-between gap-x-4 gap-y-0.5">
          <StatusDot color={timing.color} className="text-xs">
            {current ? "En camino" : timing.label}
          </StatusDot>
          <span className="num text-xs text-ink-2">
            {stop.delivered_at ? <>Estimada {formatClock(stop.eta)} · {formatDiff(stop.diff_minutes)}</> : "Hora estimada"}
          </span>
        </div>
        {stop.status === "failed" ? (
          <p className="mt-1 text-[13px] text-err">No entregada{stop.reason ? `: ${stop.reason}` : ""}</p>
        ) : null}
      </div>
    </StaggerItem>
  );
}

/** Mapa de la ruta: el camino lo decidió nuestro A*; Google solo dibuja la carretera entre esos nodos. */
function RouteMap({ detail }: { detail: RouteDetail }) {
  const network = useNetwork();
  const codes = React.useMemo(() => joinLegNodes(detail.legs), [detail.legs]);
  if (codes.length < 2) return null;
  if (!network.data) return <Skeleton className="aspect-[4/3] w-full rounded-xl" />;
  const byCode = new Map(network.data.nodes.map((n) => [n.code, n]));
  const markers: MapMarker[] = [];
  detail.route.stops.forEach((s) => {
    const node = s.node ? byCode.get(s.node.code) : undefined;
    if (node) markers.push({ id: `s${s.id}`, kind: "stop", lat: node.lat, lng: node.lng, label: String(s.sequence) });
  });
  const fitTo = codes.map((c) => byCode.get(c)).filter((n): n is NonNullable<typeof n> => !!n).map((n) => ({ lat: n.lat, lng: n.lng }));
  return (
    <section aria-label="Mapa de la ruta" className="min-w-0">
      <div className="overflow-hidden rounded-xl border border-line bg-surface p-1.5 shadow-card">
        <NetworkMap nodes={network.data.nodes} edges={network.data.edges} labels="none" width={720} height={560}
          paths={[{ codes, color: "#2f4bd8", width: 4.5, followRoads: true }]} markers={markers} fitTo={fitTo}
          ariaLabel="Mapa de la ruta con sus paradas" />
      </div>
    </section>
  );
}

function Timeline({ detail }: { detail: RouteDetail }) {
  const { route } = detail;
  // La parada actual es la primera sin resolver, solo si la ruta ya salió
  const currentId = route.status === "in_progress" ? route.stops.find((s) => s.status === "pending")?.id : undefined;
  return (
    <section aria-label="Línea de tiempo">
      <div className="mb-3 flex items-baseline justify-between gap-3">
        <h2 className="text-sm font-semibold">Paradas <span className="num font-normal text-ink-2">{route.stops.length}</span></h2>
      </div>
      {route.stops.length === 0 ? (
        <p className="text-sm text-ink-2">Esta ruta no tiene paradas.</p>
      ) : (
        <Stagger as="ol">
          {route.stops.map((s, i) => (
            <StopItem key={s.id} stop={s} last={i === route.stops.length - 1} current={s.id === currentId} />
          ))}
        </Stagger>
      )}
      <p className="mt-3 text-xs text-ink-2">
        Se marca retraso si la entrega pasa {detail.late_tolerance_min} min de la hora estimada.
      </p>
    </section>
  );
}

function SummaryStat({ label, children, hint }: { label: string; children: React.ReactNode; hint?: React.ReactNode }) {
  return (
    <div className="flex min-w-0 flex-col gap-0.5">
      <span className="text-xs text-ink-2">{label}</span>
      <span className="num text-2xl font-medium tracking-tight">{children}</span>
      {hint ? <span className="truncate text-xs text-ink-2">{hint}</span> : null}
    </div>
  );
}

function DetailSkeleton() {
  return (
    <div className="px-6 py-6 lg:px-8" aria-busy="true" aria-label="Cargando ruta">
      <Skeleton className="mb-6 h-16 w-full max-w-2xl" />
      <div className="grid gap-8 lg:grid-cols-[minmax(0,440px)_minmax(0,1fr)]">
        <div className="flex flex-col gap-2">
          {Array.from({ length: 5 }).map((_, i) => <Skeleton key={i} className="h-16 w-full" />)}
        </div>
        <Skeleton className="aspect-[4/3] w-full rounded-xl" />
      </div>
    </div>
  );
}

export function RouteDetailPage() {
  const { routeId } = useParams();
  const query = useRouteDetail(routeId);
  const detail = query.data;
  const route = detail?.route;

  return (
    <div>
      <header className="px-6 pb-4 pt-6 lg:px-8">
        <nav aria-label="Ruta de navegación" className="mb-3 flex items-center gap-1 text-[13px] text-ink-2">
          <Link to="/rutas" className="rounded-md px-1 py-0.5 hover:bg-hover hover:text-ink">Rutas</Link>
          <ChevronRightIcon className="size-3.5" aria-hidden />
          <span className="num text-ink" aria-current="page">{route?.code ?? "…"}</span>
        </nav>
        {route ? (
          <div className="flex flex-wrap items-end justify-between gap-x-8 gap-y-4">
            <div>
              <h1 className="flex items-center gap-3 text-2xl font-semibold tracking-tight">
                <span className="num">{route.code}</span>
                <StatusDot color={ROUTE_STATUS[route.status].color} className="text-sm font-normal text-ink-3">{route.status_label}</StatusDot>
              </h1>
              <p className="mt-1 text-[13px] text-ink-2">
                {route.depot} · {formatWhen(route.departure_at)}
                {route.driver ? <> · {route.driver}{route.vehicle ? ` · ${route.vehicle}` : ""}</> : <> · <span className="font-medium text-warn">Sin piloto</span></>}
              </p>
              <p className="num mt-1 text-[13px] text-ink-3">
                {route.traffic_minutes != null
                  ? `+${route.traffic_minutes.toLocaleString("es-GT", { maximumFractionDigits: 1 })} min por tráfico`
                  : "Esta ruta no tiene un desglose de tráfico guardado."}
              </p>
            </div>
            <div className="grid grid-cols-2 gap-x-8 gap-y-3 sm:grid-cols-4">
              <SummaryStat label="Tiempo de manejo" hint={`Termina ${formatClock(route.finish_at)}`}>
                <AnimatedNumber value={route.driving_minutes} format={formatMinutes} />
              </SummaryStat>
              <SummaryStat label="Distancia"><AnimatedNumber value={route.total_km} format={formatKm} /></SummaryStat>
              <SummaryStat label="Paradas"><AnimatedNumber value={route.stops.length} /></SummaryStat>
              <SummaryStat label="Ahorro vs. la más corta" hint="Con el mismo tráfico">
                {route.minutes_saved != null ? <AnimatedNumber value={route.minutes_saved} format={formatMinutes} className="text-ok" /> : "—"}
              </SummaryStat>
            </div>
          </div>
        ) : (
          <h1 className="text-2xl font-semibold tracking-tight">Detalle de ruta</h1>
        )}
      </header>

      {query.isPending ? <DetailSkeleton /> : null}
      {query.error ? <div className="p-6 lg:px-8"><ErrorNote error={query.error} /></div> : null}
      {detail && route ? (
        <div className="flex flex-col gap-10 px-6 pb-10 lg:px-8">
          <ProgressBar progress={route.progress} className="max-w-md" />

          <div className="grid grid-cols-1 items-start gap-8 lg:grid-cols-[minmax(0,440px)_minmax(0,1fr)]">
            {/* El mapa manda: va primero en móvil y se queda fijo en escritorio mientras corre la lista */}
            <div className="flex min-w-0 flex-col gap-3 lg:sticky lg:top-4 lg:order-2">
              <RouteMap detail={detail} />
              <DataSourceNote source={parseDataSource(route.data_source)} />
            </div>
            <div className="min-w-0 lg:order-1"><Timeline detail={detail} /></div>
          </div>

          <div className="grid gap-x-10 gap-y-8 border-t border-line pt-8 lg:grid-cols-2">
            <AssignmentSection route={route} />
            <LiveCheck routeId={route.id} status={route.status} />
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
            <section aria-label="Tramos">
              <details className="group">
                <summary className="mb-3 flex cursor-pointer list-none items-center gap-1.5 text-sm font-semibold">
                  <ChevronRightIcon className="size-4 text-ink-2 transition-transform group-open:rotate-90" aria-hidden />
                  Tramos <span className="num font-normal text-ink-2">{detail.legs.length}</span>
                </summary>
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
              </details>
            </section>
          </div>
        </div>
      ) : null}
    </div>
  );
}
