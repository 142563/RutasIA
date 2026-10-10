import { ArrowRightIcon, RouteIcon } from "lucide-react";
import * as React from "react";
import { Link } from "react-router";
import { Button } from "@/components/ui/button";
import { AnimatedTabs, Skeleton, Stagger, StaggerItem } from "@/components/ui/motion";
import { EmptyState, ErrorNote, PageHeader, StatusDot } from "@/components/ui/misc";
import { isUnassigned } from "@/lib/assignment";
import { formatClock, formatKm, formatMinutes } from "@/lib/format";
import { progressOf, ROUTE_STATUS, useRoutes, type RouteRow, type RouteStatus } from "@/lib/dispatch";
import { cn } from "@/lib/utils";
import { formatWhen, ProgressBar } from "./shared";

type Tab = "all" | "unassigned" | RouteStatus;

const TAB_LABELS: { value: Tab; label: string }[] = [
  { value: "all", label: "Todas" },
  { value: "unassigned", label: "Sin asignar" },
  { value: "planned", label: "Planificadas" },
  { value: "in_progress", label: "En curso" },
  { value: "completed", label: "Completadas" },
  { value: "canceled", label: "Canceladas" },
];

/** Misma grilla en el encabezado y en cada fila para que las columnas alineen. */
const GRID = "grid grid-cols-[minmax(0,1.5fr)_minmax(0,1.3fr)_minmax(0,1.2fr)_5rem_5.5rem_4.5rem_7.5rem] items-center gap-x-4";

function matches(r: RouteRow, value: Tab) {
  return value === "all" ? true : value === "unassigned" ? isUnassigned(r) : r.status === value;
}

function RouteLine({ r }: { r: RouteRow }) {
  const live = r.status === "in_progress";
  const unassigned = isUnassigned(r);
  const dim = r.status === "canceled" || r.status === "completed";
  return (
    <div className={cn("group relative transition-colors hover:bg-hover/60", dim && "text-ink-3")}>
      <div className="space-y-3 p-4 sm:hidden">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <Link to={`/rutas/${r.id}`} className="num flex min-h-11 min-w-0 items-center break-all text-sm font-medium after:absolute after:inset-0 after:content-['']">{r.code}</Link>
          <StatusDot color={ROUTE_STATUS[r.status].color}>{r.status_label}</StatusDot>
        </div>
        <p className="break-words text-[13px]">{r.driver ?? (unassigned ? "Sin asignar" : "Sin piloto")} · <span className="num">{r.vehicle ?? "Sin camión"}</span></p>
        <ProgressBar progress={progressOf(r.stops)} />
        <div className="flex flex-wrap justify-between gap-2 text-[13px]">
          <span className="num">{formatMinutes(r.driving_minutes)} · {formatKm(r.total_km)}</span>
          <span className="num text-ink-2">Termina {formatClock(r.finish_at)}</span>
        </div>
        <p className="text-xs text-ink-2">{formatWhen(r.departure_at)}</p>
        <span className="inline-flex min-h-11 items-center gap-2 text-sm font-medium">Ver detalle <ArrowRightIcon className="size-4" /></span>
      </div>
      <div className={cn(GRID, "hidden px-6 py-3 sm:grid lg:px-8")}>
        <div className="flex min-w-0 items-center gap-2.5">
          <span
            className={cn("size-2 shrink-0 rounded-full", live && "live-dot")}
            style={{ background: ROUTE_STATUS[r.status].color }}
            aria-hidden
          />
          <div className="min-w-0">
            {/* Enlace extendido: toda la fila navega y el foco por teclado cae en el código */}
            <Link to={`/rutas/${r.id}`} className="num block truncate text-[13px] font-medium text-ink after:absolute after:inset-0 after:content-['']">
              {r.code}
            </Link>
            <span className="block truncate text-xs text-ink-2">{r.status_label} · {formatWhen(r.departure_at)}</span>
          </div>
        </div>
        <div className="min-w-0">
          {r.driver ? (
            <span className="block truncate text-sm">{r.driver}</span>
          ) : unassigned ? (
            <span className="text-sm font-medium text-warn">Sin asignar</span>
          ) : (
            <span className="text-sm text-ink-2">—</span>
          )}
          <span className="num block truncate text-xs text-ink-2">{r.vehicle ?? "Sin camión"}</span>
        </div>
        <ProgressBar progress={progressOf(r.stops)} />
        <span className="num text-right text-[13px]" title="Hora estimada de término">{formatClock(r.finish_at)}</span>
        <span className="num text-right text-[13px]">{formatMinutes(r.driving_minutes)}</span>
        <span className="num text-right text-[13px]">{formatKm(r.total_km)}</span>
        <span className="flex items-center justify-end gap-2">
          <span className="num text-[13px] text-ok group-hover:hidden">{r.minutes_saved != null ? `−${formatMinutes(r.minutes_saved)}` : "—"}</span>
          <span className="hidden items-center gap-1 text-[13px] font-medium text-ink group-hover:inline-flex" aria-hidden>
            Ver detalle <ArrowRightIcon className="size-3.5" />
          </span>
        </span>
      </div>
    </div>
  );
}

function RouteSkeleton() {
  return (
    <div aria-busy="true" aria-label="Cargando rutas">
      {Array.from({ length: 6 }).map((_, i) => (
        <div key={i} className={cn(GRID, "hidden border-b border-line px-6 py-3.5 sm:grid lg:px-8")}>
          <Skeleton className="h-8 w-3/4" />
          <Skeleton className="h-8 w-2/3" />
          <Skeleton className="h-3 w-full" />
          <Skeleton className="ml-auto h-4 w-12" />
          <Skeleton className="ml-auto h-4 w-14" />
          <Skeleton className="ml-auto h-4 w-10" />
          <Skeleton className="ml-auto h-4 w-16" />
        </div>
      ))}
      <div className="space-y-3 p-4 sm:hidden">
        {[0, 1, 2].map((i) => <Skeleton key={i} className="h-44 w-full rounded-xl" />)}
      </div>
    </div>
  );
}

export function RoutesPage() {
  const [tab, setTab] = React.useState<Tab>("all");
  const routes = useRoutes();
  const all = routes.data?.routes ?? [];
  const rows = all.filter((r) => matches(r, tab));
  const count = (value: Tab) => all.filter((r) => matches(r, value)).length;
  const unassignedCount = count("unassigned");

  const options = TAB_LABELS.map((t) => ({
    value: t.value,
    label: (
      <>
        {t.label}
        {routes.data ? (
          <span className={cn("num text-xs", t.value === "unassigned" && unassignedCount > 0 ? "font-medium text-warn" : "text-ink-2")}>
            {count(t.value)}
          </span>
        ) : null}
      </>
    ),
  }));

  return (
    <div className="flex min-h-full flex-col">
      <PageHeader
        title="Rutas"
        subtitle="Las últimas 50 rutas planificadas"
        actions={<Button asChild variant="outline" className="max-sm:min-h-11"><Link to="/planificar">Planificar ruta</Link></Button>}
      />

      <div className="overflow-x-auto px-6 pb-3 pt-2 lg:px-8">
        <AnimatedTabs id="routes-status" label="Filtrar por estado" value={tab} onChange={setTab} options={options} className="max-sm:[&_button]:min-h-11" />
      </div>

      <div className="flex-1 overflow-x-auto border-t border-line">
        <div className={rows.length > 0 && !routes.isPending ? "sm:min-w-[960px]" : undefined}>
          {routes.isPending ? (
            <RouteSkeleton />
          ) : routes.error ? (
            <div className="p-6"><ErrorNote error={routes.error} /></div>
          ) : rows.length === 0 ? (
            <EmptyState icon={<RouteIcon />} title={all.length === 0 ? "Aún no hay rutas" : tab === "unassigned" ? "Todas las rutas tienen piloto" : "No hay rutas en este estado"}
              action={all.length === 0 ? <Button asChild variant="outline"><Link to="/planificar">Planificar ruta</Link></Button> : null}>
              {all.length === 0 ? "Las rutas que confirmes en Planificar aparecen aquí." : "Prueba con otro estado."}
            </EmptyState>
          ) : (
            <>
              <div className={cn(GRID, "hidden border-b border-line px-6 py-2 text-xs text-ink-2 sm:grid lg:px-8")} aria-hidden>
                <span>Ruta</span>
                <span>Piloto y camión</span>
                <span>Avance</span>
                <span className="text-right">Termina</span>
                <span className="text-right">Tiempo</span>
                <span className="text-right">Distancia</span>
                <span className="text-right">Ahorro</span>
              </div>
              {/* key = filtro: la cascada se repite al cambiar de estado */}
              <Stagger as="ul" key={tab} aria-label="Rutas" className="divide-y divide-line border-b border-line">
                {rows.map((r) => (
                  <StaggerItem as="li" key={r.id}><RouteLine r={r} /></StaggerItem>
                ))}
              </Stagger>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
