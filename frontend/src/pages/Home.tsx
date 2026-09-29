import { ArrowRightIcon } from "lucide-react";
import { Link } from "react-router";
import { DataSourceNote } from "@/components/DataSourceNote";
import { NetworkMap } from "@/components/map/NetworkMap";
import { Button } from "@/components/ui/button";
import { ErrorNote, Metric, PageHeader, Spinner } from "@/components/ui/misc";
import { useUser } from "@/lib/auth";
import { ApiError } from "@/lib/api";
import { useDashboard } from "@/lib/dispatch";
import { formatDateLong } from "@/lib/format";
import { useNetwork } from "@/lib/queries";
import { BANDS, bandFor, dayTypeFor } from "@/lib/traffic";

export function HomePage() {
  const user = useUser();
  const network = useNetwork();
  const dashboard = useDashboard();
  const kpis = dashboard.data;
  const now = new Date();
  const band = BANDS.find((b) => b.id === bandFor(now))!;
  const dayType = dayTypeFor(now) === "weekday" ? "Día laboral" : "Fin de semana";

  return (
    <div>
      <PageHeader title={`Hola, ${user.full_name.split(" ")[0]}`} subtitle={formatDateLong(now)} />
      <div className="grid gap-8 px-6 py-6 lg:grid-cols-[minmax(0,1fr)_minmax(0,420px)] lg:px-8">
        <section className="flex flex-col gap-8">
          {dashboard.error && !(dashboard.error instanceof ApiError && dashboard.error.status === 403) ? (
            <ErrorNote error={dashboard.error} />
          ) : null}
          {dashboard.error instanceof ApiError && dashboard.error.status === 403 ? null : (
            <div className="grid grid-cols-2 gap-6 border-b border-line pb-6 sm:grid-cols-3">
              <Metric label="Rutas en curso" value={kpis?.routes_in_progress ?? "—"}
                hint={<Link to="/monitoreo" className="hover:underline">Ver monitoreo</Link>} />
              <Metric label="Planificadas para hoy" value={kpis?.routes_planned_today ?? "—"}
                hint={<Link to="/rutas" className="hover:underline">Ver rutas</Link>} />
              <Metric label="Paradas con retraso" value={kpis?.delayed_stops ?? "—"}
                hint={kpis ? `ETA vencida o entrega con más de ${kpis.late_tolerance_min} min de retraso` : undefined} />
              <Metric label="Pedidos sin asignar" value={kpis?.unassigned_orders ?? "—"}
                hint={<Link to="/pedidos" className="hover:underline">Ver pedidos</Link>} />
              <Metric label="Entregas de hoy" value={kpis?.deliveries_today ?? "—"} />
            </div>
          )}
          <div className="grid grid-cols-2 gap-6 border-b border-line pb-6 sm:grid-cols-3">
            <Metric label="Franja de tráfico actual" value={band.label} hint={`${band.hours} · ${dayType}`} />
            <Metric label="Nodos del grafo" value={network.data?.nodes.length ?? "—"} hint="Cabeceras, municipios y cruces" />
            <Metric label="Tramos" value={network.data?.edges.length ?? "—"} hint="Cada uno con ida y vuelta" />
          </div>
          <DataSourceNote source={network.data?.data_source} />
          <div className="flex flex-col gap-2">
            <h2 className="text-sm font-semibold">Cómo se usa</h2>
            {[
              { to: "/pedidos", title: "Pedidos", text: "Registra los paquetes con su dirección y marca cuáles salen hoy." },
              { to: "/planificar", title: "Planificar", text: "Eliges la hora de salida y el sistema propone la ruta más rápida con el tráfico de esa hora." },
              { to: "/rutas", title: "Asignar y seguir", text: "Confirmas con un conductor: él ve la ruta en su celular y tú el avance en Monitoreo." },
            ].map((item, i) => (
              <Link key={item.to} to={item.to} className="group flex items-center gap-4 border-b border-line py-3 last:border-b-0">
                <span className="num grid size-7 shrink-0 place-items-center rounded-full bg-ink text-xs font-semibold text-white">{i + 1}</span>
                <span className="flex-1">
                  <span className="block text-sm font-medium">{item.title}</span>
                  <span className="block text-[13px] text-ink-2">{item.text}</span>
                </span>
                <ArrowRightIcon className="size-4 text-ink-2 transition-transform group-hover:translate-x-0.5 group-hover:text-ink" />
              </Link>
            ))}
            <p className="pt-1 text-[13px] text-ink-2">
              Para la defensa: en <Link to="/laboratorio" className="underline">Laboratorio</Link> se ven Dijkstra y A* lado a lado.
            </p>
          </div>
          <Button asChild variant="outline" className="self-start">
            <Link to="/planificar">Planificar rutas de hoy</Link>
          </Button>
        </section>
        <section aria-label="Red vial" className="rounded-xl border border-line bg-surface p-2">
          {network.isPending ? <div className="p-6"><Spinner /></div> : null}
          {network.error ? <div className="p-4"><ErrorNote error={network.error} /></div> : null}
          {network.data ? <NetworkMap nodes={network.data.nodes} edges={network.data.edges} /> : null}
        </section>
      </div>
    </div>
  );
}
