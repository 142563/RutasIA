import { ArrowRightIcon, CircleCheckIcon, MegaphoneIcon, TriangleAlertIcon } from "lucide-react";
import { AnimatePresence, motion } from "motion/react";
import * as React from "react";
import { Link } from "react-router";
import { NetworkMap, type MapMarker } from "@/components/map/NetworkMap";
import { Button } from "@/components/ui/button";
import { ErrorNote, PageHeader } from "@/components/ui/misc";
import { AnimatedNumber, AnimatedTabs, EASE, Skeleton, Stagger } from "@/components/ui/motion";
import { useUser } from "@/lib/auth";
import { useDashboard, useMonitoring } from "@/lib/dispatch";
import { formatDateLong } from "@/lib/format";
import { useDepots, useOrders } from "@/lib/orders";
import { useNetwork } from "@/lib/queries";
import { nextStep } from "@/lib/today";
import { BANDS, bandFor, type Band } from "@/lib/traffic";
import { cn } from "@/lib/utils";
import { useIncidents } from "@/lib/incidents";
import {
  IncidentItem, PresenceList, ProposalItem, ReportIncidentForm, RouteItem, RouteRowSkeleton, RowSkeleton, Section,
} from "@/pages/monitoring/parts";

/** Cómo suele estar el tráfico en cada franja: punto de color + palabra, sin jerga. */
const BAND_FEEL: Record<Band, { word: string; dot: string }> = {
  dawn: { word: "fluido", dot: "bg-ok" },
  peak_am: { word: "pesado", dot: "bg-err" },
  mid_morning: { word: "moderado", dot: "bg-warn" },
  midday: { word: "moderado", dot: "bg-warn" },
  afternoon: { word: "moderado", dot: "bg-warn" },
  peak_pm: { word: "pesado", dot: "bg-err" },
  night: { word: "fluido", dot: "bg-ok" },
};

type FeedTab = "reroutes" | "incidents";

/** Una cifra de la franja de indicadores; clicable si tiene destino. */
function Kpi({ label, value, hint, to, alert }: {
  label: string; value: number | undefined; hint?: string; to?: string; alert?: boolean;
}) {
  const body = (
    <>
      <span className="text-xs text-ink-2">{label}</span>
      <span className={cn("num text-3xl font-medium leading-none tracking-tight", alert && "text-warn")}>
        <AnimatedNumber value={value} />
      </span>
      <span className="min-h-4 text-xs text-ink-2">{hint}</span>
    </>
  );
  // Sin sangría al inicio de cada fila: la 1.ª y 3.ª en celular (2 columnas), solo la 1.ª con 4
  const base = "flex flex-col gap-1.5 px-5 py-4 odd:pl-0 sm:odd:pl-5 sm:first:pl-0";
  return to ? (
    <Link to={to} className={cn(base, "rounded-lg transition-colors hover:bg-hover")}>{body}</Link>
  ) : <div className={base}>{body}</div>;
}

/**
 Hoy: lo que está pasando y qué hacer ahora. Reúne el inicio y el monitoreo en vivo
 (se actualiza solo) para que el despachador no tenga que buscar en varias pantallas.
*/
export function HomePage() {
  const user = useUser();
  const dashboard = useDashboard();
  const monitoring = useMonitoring();
  const incidents = useIncidents();
  const [reporting, setReporting] = React.useState(false);
  const [tab, setTab] = React.useState<FeedTab | null>(null);
  const reroutes = incidents.data?.reroutes ?? [];
  const vigentes = incidents.data?.incidents ?? [];
  const network = useNetwork();
  const pending = useOrders({ status: "pending" });
  const depots = useDepots();
  const now = new Date();
  const band = BANDS.find((b) => b.id === bandFor(now))!;
  const feel = BAND_FEEL[band.id];

  const kpis = dashboard.data;
  const live = monitoring.data;
  const step = kpis && live
    ? nextStep({
        pendingOrders: kpis.unassigned_orders,
        routesInProgress: kpis.routes_in_progress,
        routesPlannedToday: kpis.routes_planned_today,
        delayedStops: kpis.delayed_stops,
        pendingReroutes: reroutes.length,
      })
    : null;

  // Pestaña activa: la elegida o, si no hay, la que tenga algo pendiente (recálculos primero).
  const activeTab: FeedTab = tab ?? (reroutes.length === 0 && vigentes.length > 0 ? "incidents" : "reroutes");

  const markers: MapMarker[] = [
    ...(depots.data?.depots ?? []).map((d) => ({ id: `d${d.id}`, kind: "depot" as const, lat: d.latitude, lng: d.longitude, label: d.name })),
    ...(pending.data?.orders ?? []).map((o) => ({ id: `o${o.id}`, kind: "dot" as const, lat: o.latitude, lng: o.longitude, label: `${o.recipient} · ${o.node?.name ?? ""}` })),
  ];
  const pendingCount = pending.data?.orders.length ?? 0;

  return (
    <div>
      <PageHeader
        title={`Hola, ${user.full_name.split(" ")[0]}`}
        subtitle={(
          <span className="flex flex-wrap items-center gap-x-3 gap-y-1.5">
            <span>{formatDateLong(now)}</span>
            <span className="inline-flex items-center gap-2 rounded-full border border-line bg-surface px-2.5 py-0.5 text-xs text-ink-3">
              <span className={cn("size-2 rounded-full", feel.dot)} aria-hidden />
              {band.label} · tráfico {feel.word}
              <span className="num text-ink-2">{band.hours}</span>
            </span>
          </span>
        )}
      />
      <div className="grid gap-8 px-6 py-6 lg:grid-cols-[minmax(0,1fr)_minmax(0,560px)] lg:px-8">
        <section className="flex min-w-0 flex-col gap-8">
          {dashboard.error ? <ErrorNote error={dashboard.error} /> : null}

          {/* Protagonista: el siguiente paso. Si hay algo urgente, acento lateral naranja. */}
          {step ? (
            <motion.div
              initial={{ opacity: 0, y: 14, scale: 0.985 }}
              animate={{ opacity: 1, y: 0, scale: 1 }}
              transition={{ duration: 0.4, ease: EASE }}
              className={cn(
                "flex flex-col gap-5 rounded-xl border border-line bg-surface p-6 shadow-lift sm:flex-row sm:items-center sm:justify-between",
                step.tone === "warn" && "border-l-4 border-l-delivery",
              )}
            >
              <div className="flex gap-3">
                {step.tone === "warn" ? <TriangleAlertIcon className="mt-1 size-5 shrink-0 text-delivery" aria-hidden /> : null}
                {step.tone === "ok" ? <CircleCheckIcon className="mt-1 size-5 shrink-0 text-ok" aria-hidden /> : null}
                <div>
                  <p className="text-xs font-medium uppercase tracking-wide text-ink-2">Siguiente paso</p>
                  <p className="mt-1 text-xl font-semibold tracking-tight">{step.title}</p>
                  <p className="mt-1 max-w-prose text-[13px] text-ink-2">{step.text}</p>
                </div>
              </div>
              {step.cta ? (
                <Button asChild size="lg" className="shrink-0">
                  <Link to={step.cta.to}>{step.cta.label} <ArrowRightIcon /></Link>
                </Button>
              ) : null}
            </motion.div>
          ) : (
            <div className="rounded-xl border border-line bg-surface p-6 shadow-card" role="status" aria-label="Cargando el siguiente paso">
              <Skeleton className="h-3 w-24" />
              <Skeleton className="mt-3 h-6 w-2/3" />
              <Skeleton className="mt-2 h-4 w-1/2" />
            </div>
          )}

          {/* Franja de indicadores */}
          {kpis ? (
            <div className="grid grid-cols-2 border-y border-line py-1 sm:grid-cols-4 [&>*:nth-child(even)]:border-l [&>*]:border-line sm:[&>*:not(:first-child)]:border-l">
              <Kpi label="Rutas en camino" value={kpis.routes_in_progress} to="/rutas" />
              <Kpi label="Pedidos sin ruta" value={kpis.unassigned_orders} to="/pedidos" hint="Ver pedidos" />
              <Kpi label="Entregas de hoy" value={kpis.deliveries_today} />
              <Kpi label="Con retraso" value={kpis.delayed_stops} alert={kpis.delayed_stops > 0}
                to={kpis.delayed_stops > 0 ? "/rutas" : undefined} hint={`más de ${kpis.late_tolerance_min} min`} />
            </div>
          ) : (
            <div className="grid grid-cols-2 gap-5 border-y border-line py-4 sm:grid-cols-4" aria-hidden>
              {[0, 1, 2, 3].map((i) => <div key={i} className="space-y-2"><Skeleton className="h-3 w-20" /><Skeleton className="h-8 w-12" /></div>)}
            </div>
          )}

          <Section title="Rutas de hoy" count={live?.routes.length}>
            {!live
              ? <div><RouteRowSkeleton /><RouteRowSkeleton /></div>
              : live.routes.length === 0
                ? <p className="py-4 text-[13px] text-ink-2">Todavía no hay rutas para hoy. Cuando asignes una, verás aquí su avance en vivo.</p>
                : <Stagger as="ul">{live.routes.map((r) => <RouteItem key={r.id} route={r} />)}</Stagger>}
          </Section>

          {/* Recálculos e incidentes comparten espacio en pestañas para acortar la página */}
          <section>
            <div className="flex flex-wrap items-center justify-between gap-2 border-b border-line pb-2">
              <AnimatedTabs<FeedTab> id="home-feed" label="Novedades de la carretera" value={activeTab} onChange={setTab}
                options={[
                  { value: "reroutes", label: <>Recálculos <span className="num text-xs text-ink-2">{reroutes.length}</span></> },
                  { value: "incidents", label: <>Incidentes <span className="num text-xs text-ink-2">{vigentes.length}</span></> },
                ]} />
              {activeTab === "incidents" && !reporting ? (
                <Button variant="outline" size="sm" onClick={() => setReporting(true)}><MegaphoneIcon /> Reportar incidente</Button>
              ) : null}
            </div>

            <AnimatePresence mode="wait" initial={false}>
              <motion.div key={activeTab}
                initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }}
                transition={{ duration: 0.18, ease: EASE }}>
                {incidents.isError ? <div className="pt-3"><ErrorNote error={incidents.error} /></div>
                  : incidents.isPending ? <div><RowSkeleton /><RowSkeleton /></div>
                  : activeTab === "reroutes" ? (
                    reroutes.length === 0
                      ? <p className="py-4 text-[13px] text-ink-2">Ninguna ruta necesita cambios por ahora.</p>
                      : <PresenceList>{reroutes.map((r) => (
                          <ProposalItem key={r.id} reroute={r} driver={live?.routes.find((x) => x.id === r.route_id)?.driver} />
                        ))}</PresenceList>
                  ) : (
                    <>
                      {vigentes.length === 0
                        ? <p className="py-4 text-[13px] text-ink-2">No hay incidentes vigentes.</p>
                        : <PresenceList>{vigentes.map((i) => <IncidentItem key={i.id} incident={i} />)}</PresenceList>}
                      <AnimatePresence initial={false}>
                        {reporting ? (
                          <motion.div key="form" className="overflow-hidden"
                            initial={{ opacity: 0, height: 0 }} animate={{ opacity: 1, height: "auto" }} exit={{ opacity: 0, height: 0 }}
                            transition={{ duration: 0.25, ease: EASE }}>
                            <div className="pt-4"><ReportIncidentForm onDone={() => setReporting(false)} /></div>
                          </motion.div>
                        ) : null}
                      </AnimatePresence>
                    </>
                  )}
              </motion.div>
            </AnimatePresence>
          </section>
        </section>

        <section aria-label="Pedidos pendientes en el mapa" className="flex flex-col gap-2 lg:sticky lg:top-20 lg:self-start">
          <div className="overflow-hidden rounded-xl border border-line bg-surface p-2 shadow-card">
            {network.data ? (
              <NetworkMap nodes={network.data.nodes} edges={network.data.edges} markers={markers} labels="none"
                width={560} height={640} ariaLabel="Mapa de Guatemala con los pedidos pendientes" />
            ) : <Skeleton className="h-[480px] w-full" />}
          </div>
          <div className="flex flex-wrap items-center justify-between gap-x-4 gap-y-1 px-1 text-xs text-ink-2">
            <p className="flex flex-wrap gap-x-4 gap-y-1">
              <span className="flex items-center gap-1.5"><span className="size-2.5 rounded-full bg-accent" /> Pedido sin ruta</span>
              <span className="flex items-center gap-1.5"><span className="size-2.5 rounded-sm bg-ink" /> Bodega</span>
            </p>
            <span className="num">{pendingCount} {pendingCount === 1 ? "pedido" : "pedidos"} por asignar</span>
          </div>
        </section>
      </div>
    </div>
  );
}
