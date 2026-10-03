import { ArrowRightIcon, CircleCheckIcon, MegaphoneIcon, TriangleAlertIcon } from "lucide-react";
import * as React from "react";
import { Link } from "react-router";
import { NetworkMap, type MapMarker } from "@/components/map/NetworkMap";
import { Button } from "@/components/ui/button";
import { ErrorNote, Metric, PageHeader, Spinner } from "@/components/ui/misc";
import { useUser } from "@/lib/auth";
import { useDashboard, useMonitoring } from "@/lib/dispatch";
import { formatDateLong } from "@/lib/format";
import { useDepots, useOrders } from "@/lib/orders";
import { useNetwork } from "@/lib/queries";
import { nextStep } from "@/lib/today";
import { BANDS, bandFor } from "@/lib/traffic";
import { cn } from "@/lib/utils";
import { useIncidents } from "@/lib/incidents";
import { IncidentItem, ProposalItem, ReportIncidentForm, RouteItem, Section } from "@/pages/monitoring/parts";

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
  const reroutes = incidents.data?.reroutes ?? [];
  const vigentes = incidents.data?.incidents ?? [];
  const network = useNetwork();
  const pending = useOrders({ status: "pending" });
  const depots = useDepots();
  const now = new Date();
  const band = BANDS.find((b) => b.id === bandFor(now))!;

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

  const markers: MapMarker[] = [
    ...(depots.data?.depots ?? []).map((d) => ({ id: `d${d.id}`, kind: "depot" as const, lat: d.latitude, lng: d.longitude, label: d.name })),
    ...(pending.data?.orders ?? []).map((o) => ({ id: `o${o.id}`, kind: "dot" as const, lat: o.latitude, lng: o.longitude, label: `${o.recipient} · ${o.node?.name ?? ""}` })),
  ];

  return (
    <div>
      <PageHeader title={`Hola, ${user.full_name.split(" ")[0]}`}
        subtitle={`${formatDateLong(now)} · tráfico de ${band.label.toLowerCase()} (${band.hours})`} />
      <div className="grid gap-8 px-6 py-6 lg:grid-cols-[minmax(0,1fr)_minmax(0,460px)] lg:px-8">
        <section className="flex min-w-0 flex-col gap-8">
          {dashboard.error ? <ErrorNote error={dashboard.error} /> : null}
          {step ? (
            <div className={cn(
              "flex flex-col gap-4 rounded-xl border p-5 sm:flex-row sm:items-center sm:justify-between",
              step.tone === "warn" ? "border-warn/30 bg-warn/5" : "border-line bg-surface",
            )}>
              <div className="flex gap-3">
                {step.tone === "warn" ? <TriangleAlertIcon className="mt-0.5 size-5 shrink-0 text-warn" aria-hidden /> : null}
                {step.tone === "ok" ? <CircleCheckIcon className="mt-0.5 size-5 shrink-0 text-ok" aria-hidden /> : null}
                <div>
                  <p className="text-xs text-ink-2">Siguiente paso</p>
                  <p className="text-lg font-semibold tracking-tight">{step.title}</p>
                  <p className="mt-0.5 text-[13px] text-ink-2">{step.text}</p>
                </div>
              </div>
              {step.cta ? (
                <Button asChild size="lg" className="shrink-0">
                  <Link to={step.cta.to}>{step.cta.label} <ArrowRightIcon /></Link>
                </Button>
              ) : null}
            </div>
          ) : <Spinner />}

          <div className="grid grid-cols-2 gap-6 border-b border-line pb-6 sm:grid-cols-4">
            <Metric label="Rutas en camino" value={kpis?.routes_in_progress ?? "—"} />
            <Metric label="Pedidos sin ruta" value={kpis?.unassigned_orders ?? "—"}
              hint={<Link to="/pedidos" className="hover:underline">Ver pedidos</Link>} />
            <Metric label="Entregas de hoy" value={kpis?.deliveries_today ?? "—"} />
            <Metric label="Con retraso" value={kpis?.delayed_stops ?? "—"}
              hint={kpis ? `más de ${kpis.late_tolerance_min} min` : undefined} />
          </div>

          {live ? (
            <Section title="Rutas de hoy" count={live.routes.length}>
              {live.routes.length === 0
                ? <p className="py-4 text-[13px] text-ink-2">Todavía no hay rutas para hoy. Cuando asignes una, verás aquí su avance en vivo.</p>
                : <ul>{live.routes.map((r) => <RouteItem key={r.id} route={r} />)}</ul>}
            </Section>
          ) : null}
          <Section title="Recálculos pendientes" count={reroutes.length}>
            {incidents.isError ? <ErrorNote error={incidents.error} />
              : incidents.isPending ? <p className="py-4"><Spinner /></p>
              : reroutes.length === 0
                ? <p className="py-4 text-[13px] text-ink-2">Ninguna ruta necesita cambios por ahora.</p>
                : <ul>{reroutes.map((r) => (
                    <ProposalItem key={r.id} reroute={r} driver={live?.routes.find((x) => x.id === r.route_id)?.driver} />
                  ))}</ul>}
          </Section>
          <Section title="Incidentes en la carretera" count={vigentes.length}>
            {incidents.isError ? null
              : incidents.isPending ? <p className="py-4"><Spinner /></p>
              : vigentes.length === 0
                ? <p className="py-4 text-[13px] text-ink-2">No hay incidentes vigentes.</p>
                : <ul>{vigentes.map((i) => <IncidentItem key={i.id} incident={i} />)}</ul>}
            <div className="pt-4">
              {reporting
                ? <ReportIncidentForm onDone={() => setReporting(false)} />
                : <Button variant="outline" onClick={() => setReporting(true)}><MegaphoneIcon /> Reportar incidente</Button>}
            </div>
          </Section>
        </section>

        <section aria-label="Pedidos pendientes en el mapa" className="flex flex-col gap-2 lg:sticky lg:top-6 lg:self-start">
          <div className="overflow-hidden rounded-xl border border-line bg-surface p-2">
            {network.data ? (
              <NetworkMap nodes={network.data.nodes} edges={network.data.edges} markers={markers} labels="none"
                width={460} height={520} ariaLabel="Mapa de Guatemala con los pedidos pendientes" />
            ) : <div className="p-6"><Spinner label="Cargando mapa…" /></div>}
          </div>
          <p className="flex flex-wrap gap-x-4 gap-y-1 px-1 text-xs text-ink-2">
            <span className="flex items-center gap-1.5"><span className="size-2.5 rounded-full bg-accent" /> Pedido sin ruta</span>
            <span className="flex items-center gap-1.5"><span className="size-2.5 rounded-sm bg-ink" /> Bodega</span>
          </p>
        </section>
      </div>
    </div>
  );
}
