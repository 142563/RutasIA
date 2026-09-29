import { CheckIcon, LogOutIcon, TruckIcon, XIcon } from "lucide-react";
import { Link } from "react-router";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { EmptyState, ErrorNote, Spinner } from "@/components/ui/misc";
import { useLogout, useUser } from "@/lib/auth";
import { nextStop, routeProgress, useDriverToday, useStartRoute, type DriverRoute, type DriverStop } from "@/lib/driver";
import { formatClock, formatDateLong, formatKm } from "@/lib/format";
import { cn } from "@/lib/utils";
import { AlternativeRouteNotice } from "./AlternativeRouteNotice";

/** Conductor · Mi ruta de hoy (docs/prototipo/Conductor-Hoy.dc.html). Móvil primero, sin AppShell. */
export function DriverTodayPage() {
  const user = useUser();
  const today = useDriverToday();
  const logout = useLogout();
  const firstName = (today.data?.driver.name ?? user.full_name ?? user.username).split(" ")[0];

  return (
    <div className="mx-auto flex min-h-dvh w-full max-w-[480px] flex-col gap-6 bg-surface px-6 pb-10 pt-8">
      <header className="flex items-start gap-3">
        <div className="flex flex-1 flex-col gap-1">
          <span className="text-[13px] text-ink-2">{formatDateLong(new Date())}</span>
          <h1 className="text-[26px] font-semibold leading-tight tracking-tight">Hola, {firstName}</h1>
        </div>
        <Button
          variant="ghost"
          className="size-11 shrink-0"
          aria-label="Cerrar sesión"
          title="Cerrar sesión"
          disabled={logout.isPending}
          onClick={() => logout.mutate()}
        >
          <LogOutIcon />
        </Button>
      </header>

      {today.isPending ? (
        <div className="flex justify-center py-16">
          <Spinner label="Cargando tu ruta…" />
        </div>
      ) : today.isError ? (
        <div className="flex flex-col gap-3">
          <ErrorNote error={today.error} />
          <Button variant="outline" className="h-12" onClick={() => today.refetch()}>
            Reintentar
          </Button>
        </div>
      ) : today.data.routes.length === 0 ? (
        <EmptyState icon={<TruckIcon />} title="No tienes ruta para hoy">
          Cuando el despachador te asigne una, aparecerá aquí.
        </EmptyState>
      ) : (
        today.data.routes.map((route) => <RouteSection key={route.id} route={route} />)
      )}
    </div>
  );
}

function RouteSection({ route }: { route: DriverRoute }) {
  const start = useStartRoute();
  const progress = routeProgress(route);
  const next = route.status === "in_progress" ? nextStop(route) : undefined;
  const stops = [...route.stops].sort((a, b) => a.sequence - b.sequence);

  function onStart() {
    start.mutate(route.id, {
      onSuccess: () => toast.success("Ruta iniciada. ¡Buen viaje!"),
      onError: (error) => toast.error(error.message),
    });
  }

  return (
    <section aria-label={`Ruta ${route.code}`} className="flex flex-col gap-6">
      <div className="flex flex-col gap-2.5">
        <div className="flex items-baseline justify-between gap-3">
          <span className="text-[15px]">
            <span className="font-semibold">{progress.done}</span> de {progress.total} entregas
          </span>
          <span className="num text-xs text-ink-2">
            {route.code}
            {route.vehicle ? ` · ${route.vehicle}` : ""}
          </span>
        </div>
        <div
          role="progressbar"
          aria-valuemin={0}
          aria-valuemax={progress.total}
          aria-valuenow={progress.done}
          className="h-1 overflow-hidden rounded-full bg-line"
        >
          <div className="h-1 rounded-full bg-ink transition-[width]" style={{ width: `${progress.percent}%` }} />
        </div>
        <span className="text-[13px] text-ink-2">
          {formatKm(route.total_km)} · salida <span className="num">{formatClock(route.departure_at)}</span>
          {route.status === "completed" ? " · ruta completada" : null}
        </span>
      </div>

      <AlternativeRouteNotice />

      {route.status === "planned" ? (
        <Button className="h-12 rounded-xl text-[15px]" onClick={onStart} disabled={start.isPending}>
          {start.isPending ? "Iniciando…" : "Iniciar ruta"}
        </Button>
      ) : null}
      {start.isError ? <ErrorNote error={start.error} /> : null}

      <ol aria-label="Paradas" className="flex flex-col">
        {stops.map((stop) => (
          <StopRow key={stop.id} stop={stop} highlighted={next?.id === stop.id} />
        ))}
      </ol>
    </section>
  );
}

function StopRow({ stop, highlighted }: { stop: DriverStop; highlighted: boolean }) {
  if (highlighted) {
    return (
      <li className="flex flex-col gap-3.5 border-b border-line py-[18px]">
        <div className="flex items-start gap-3.5">
          <span className="num flex size-6 shrink-0 items-center justify-center rounded-full bg-accent text-xs text-white">
            {stop.sequence}
          </span>
          <span className="flex min-w-0 flex-1 flex-col gap-0.5">
            <span className="text-xs font-medium text-accent">
              Siguiente · llegada <span className="num">{formatClock(stop.eta)}</span>
            </span>
            <span className="text-[17px] font-semibold tracking-tight">{stop.recipient || stop.order_code}</span>
            <span className="text-sm text-ink-3">{stop.address}</span>
          </span>
        </div>
        <Button asChild className="ml-[38px] h-12 rounded-xl text-[15px]">
          <Link to={`/conductor/paradas/${stop.id}`}>Abrir parada</Link>
        </Button>
      </li>
    );
  }

  const marked = stop.status !== "pending";
  return (
    <li className="border-b border-line last:border-b-0">
      <Link
        to={`/conductor/paradas/${stop.id}`}
        className="flex min-h-14 items-center gap-3.5 py-3.5 focus-visible:rounded-lg"
      >
        <span className="flex w-6 shrink-0 justify-center">
          {stop.status === "delivered" ? (
            <CheckIcon className="size-4 text-ok" aria-label="Entregado" />
          ) : stop.status === "failed" ? (
            <XIcon className="size-4 text-err" aria-label="No entregado" />
          ) : (
            <span className="num text-xs text-ink-3">{stop.sequence}</span>
          )}
        </span>
        <span className="flex min-w-0 flex-1 flex-col gap-0.5">
          <span className={cn("truncate text-sm", marked ? "text-ink-2" : "text-ink")}>{stop.recipient || stop.order_code}</span>
          <span className="truncate text-[13px] text-ink-2">
            {stop.status === "failed" && stop.reason ? `No entregado · ${stop.reason}` : stop.address}
          </span>
        </span>
        <span className="num text-xs text-ink-2">{formatClock(stop.delivered_at ?? stop.eta)}</span>
      </Link>
    </li>
  );
}
