import { RouteIcon } from "lucide-react";
import * as React from "react";
import { Link, useNavigate } from "react-router";
import { Button } from "@/components/ui/button";
import { EmptyState, ErrorNote, PageHeader, Spinner, StatusDot } from "@/components/ui/misc";
import { formatKm, formatMinutes } from "@/lib/format";
import { progressOf, ROUTE_STATUS, useRoutes, type RouteStatus } from "@/lib/dispatch";
import { cn } from "@/lib/utils";
import { formatWhen, ProgressBar } from "./shared";

const TABS: { value: "all" | RouteStatus; label: string }[] = [
  { value: "all", label: "Todas" },
  { value: "planned", label: "Planificadas" },
  { value: "in_progress", label: "En curso" },
  { value: "completed", label: "Completadas" },
  { value: "canceled", label: "Canceladas" },
];

export function RoutesPage() {
  const navigate = useNavigate();
  const [tab, setTab] = React.useState<"all" | RouteStatus>("all");
  const routes = useRoutes();
  const all = routes.data?.routes ?? [];
  const rows = tab === "all" ? all : all.filter((r) => r.status === tab);
  const count = (value: "all" | RouteStatus) => (value === "all" ? all.length : all.filter((r) => r.status === value).length);

  return (
    <div className="flex min-h-full flex-col">
      <PageHeader
        title="Rutas"
        subtitle="Las últimas 50 rutas planificadas"
        actions={<Button asChild variant="outline"><Link to="/planificar">Planificar ruta</Link></Button>}
      />

      <div role="tablist" aria-label="Estado" className="flex gap-1 overflow-x-auto border-b border-line px-6 lg:px-8">
        {TABS.map((t) => (
          <button
            key={t.value}
            role="tab"
            aria-selected={tab === t.value}
            onClick={() => setTab(t.value)}
            className={cn(
              "-mb-px flex h-11 items-center gap-1.5 whitespace-nowrap border-b-2 px-2.5 text-[13px] text-ink-2 transition-colors hover:text-ink",
              tab === t.value ? "border-ink font-medium text-ink" : "border-transparent",
            )}
          >
            {t.label}
            <span className="num text-xs text-ink-2">{count(t.value)}</span>
          </button>
        ))}
      </div>

      <div className="flex-1 overflow-x-auto">
        {routes.isPending ? <div className="p-8"><Spinner /></div> : null}
        {routes.error ? <div className="p-6"><ErrorNote error={routes.error} /></div> : null}
        {routes.data && rows.length === 0 ? (
          <EmptyState icon={<RouteIcon />} title={all.length === 0 ? "Aún no hay rutas" : "No hay rutas en este estado"}
            action={all.length === 0 ? <Button asChild variant="outline"><Link to="/planificar">Planificar ruta</Link></Button> : null}>
            {all.length === 0 ? "Las rutas que confirmes en Planificar aparecen aquí." : "Prueba con otro estado."}
          </EmptyState>
        ) : null}
        {rows.length > 0 ? (
          <table className="w-full min-w-[980px] text-sm">
            <thead>
              <tr className="border-b border-line text-left text-xs text-ink-2">
                <th className="py-2.5 pl-6 pr-4 font-normal lg:pl-8">Código</th>
                <th className="py-2.5 pr-4 font-normal">Conductor</th>
                <th className="py-2.5 pr-4 font-normal">Vehículo</th>
                <th className="py-2.5 pr-4 font-normal">Salida</th>
                <th className="py-2.5 pr-4 font-normal">Estado</th>
                <th className="w-44 py-2.5 pr-4 font-normal">Progreso</th>
                <th className="py-2.5 pr-4 text-right font-normal">Tiempo</th>
                <th className="py-2.5 pr-4 text-right font-normal">Distancia</th>
                <th className="py-2.5 pr-6 text-right font-normal lg:pr-8">Ahorro</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => (
                <tr key={r.id} onClick={() => navigate(`/rutas/${r.id}`)}
                  className="cursor-pointer border-b border-line transition-colors hover:bg-hover/50">
                  <td className="num whitespace-nowrap py-3 pl-6 pr-4 text-[13px] lg:pl-8">
                    <Link to={`/rutas/${r.id}`} className="font-medium text-ink hover:underline" onClick={(e) => e.stopPropagation()}>
                      {r.code}
                    </Link>
                  </td>
                  <td className="py-3 pr-4">{r.driver ?? <span className="text-ink-2">Sin asignar</span>}</td>
                  <td className="num whitespace-nowrap py-3 pr-4 text-[13px] text-ink-3">{r.vehicle ?? "—"}</td>
                  <td className="num whitespace-nowrap py-3 pr-4 text-[13px] text-ink-3">{formatWhen(r.departure_at)}</td>
                  <td className="whitespace-nowrap py-3 pr-4">
                    <StatusDot color={ROUTE_STATUS[r.status].color}>{r.status_label}</StatusDot>
                  </td>
                  <td className="py-3 pr-4"><ProgressBar progress={progressOf(r.stops)} /></td>
                  <td className="num whitespace-nowrap py-3 pr-4 text-right">{formatMinutes(r.driving_minutes)}</td>
                  <td className="num whitespace-nowrap py-3 pr-4 text-right">{formatKm(r.total_km)}</td>
                  <td className="num whitespace-nowrap py-3 pr-6 text-right lg:pr-8">
                    {r.minutes_saved != null ? formatMinutes(r.minutes_saved) : "—"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : null}
      </div>
    </div>
  );
}
