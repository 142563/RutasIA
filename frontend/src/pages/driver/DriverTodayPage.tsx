import { CheckIcon, ChevronRightIcon, NavigationIcon, PlayIcon, TruckIcon, XIcon } from "lucide-react";
import { motion } from "motion/react";
import { Link } from "react-router";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { AnimatedNumber, Card, EASE, Skeleton, Stagger, StaggerItem } from "@/components/ui/motion";
import { EmptyState, ErrorNote } from "@/components/ui/misc";
import { useUser } from "@/lib/auth";
import { navigationUrl, nextStop, routeProgress, useDriverToday, useStartRoute, type DriverRoute, type DriverStop } from "@/lib/driver";
import { formatClock, formatDateLong, formatKm } from "@/lib/format";
import { cn } from "@/lib/utils";
import { AlternativeRouteNotice } from "./AlternativeRouteNotice";
import { AnimatedCheck, DriverHeader, DriverPage, ProgressBar } from "./parts";
import { ReportIncident } from "./ReportIncident";
import { LocationSharing } from "./LocationSharing";

/** Conductor · Mi ruta de hoy (docs/prototipo/Conductor-Hoy.dc.html). Móvil primero, sin AppShell. */
export function DriverTodayPage() {
  const user = useUser();
  const today = useDriverToday();
  const fullName = today.data?.driver.name ?? user.full_name ?? user.username;
  const firstName = fullName.split(" ")[0];

  return (
    <DriverPage>
      <DriverHeader name={fullName} />
      <main className="flex flex-1 flex-col gap-5 px-4 pb-10 pt-5">
        <div className="flex flex-col gap-0.5">
          <span className="text-[13px] capitalize text-ink-2">{formatDateLong(new Date())}</span>
          <h1 className="text-[26px] font-semibold leading-tight tracking-tight">Hola, {firstName}</h1>
        </div>

        {today.isPending ? (
          <div className="flex flex-col gap-4" role="status" aria-label="Cargando tu ruta">
            <Skeleton className="h-24" />
            <Skeleton className="h-64 rounded-2xl" />
            <Skeleton className="h-14" />
            <Skeleton className="h-14" />
          </div>
        ) : today.isError ? (
          <div className="flex flex-col gap-3">
            <ErrorNote error={today.error} />
            <Button variant="outline" className="h-12 rounded-xl text-[15px]" onClick={() => today.refetch()}>
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
      </main>
    </DriverPage>
  );
}

function RouteSection({ route }: { route: DriverRoute }) {
  const start = useStartRoute();
  const progress = routeProgress(route);
  const inProgress = route.status === "in_progress";
  const next = inProgress ? nextStop(route) : undefined;
  const stops = [...route.stops].sort((a, b) => a.sequence - b.sequence);
  const rest = stops.filter((s) => s.id !== next?.id);
  const allDone = progress.total > 0 && progress.done === progress.total;

  function onStart() {
    start.mutate(route.id, {
      onSuccess: () => toast.success("Ruta iniciada. ¡Buen viaje!"),
      onError: (error) => toast.error(error.message),
    });
  }

  return (
    <section aria-label={`Ruta ${route.code}`} className="flex flex-col gap-5">
      <Card className="flex flex-col gap-3 p-4">
        <div className="flex items-end justify-between gap-3">
          <div className="flex items-baseline gap-1.5">
            <AnimatedNumber value={progress.done} className="text-[34px] font-medium leading-none tracking-tight" />
            <span className="text-[15px] text-ink-2">
              de <span className="num">{progress.total}</span> entregas
            </span>
          </div>
          <span className="num text-xs text-ink-2">
            {route.code}
            {route.vehicle ? ` · ${route.vehicle}` : ""}
          </span>
        </div>
        <ProgressBar done={progress.done} total={progress.total} percent={progress.percent} />
        <span className="text-[13px] text-ink-2">
          {formatKm(route.total_km)} · salida <span className="num">{formatClock(route.departure_at)}</span>
          {route.status === "completed" ? " · ruta completada" : null}
        </span>
      </Card>

      <AlternativeRouteNotice route={route} />
      <LocationSharing routeId={route.id} active={inProgress} />

      {route.status === "planned" ? (
        <Button className="h-14 rounded-xl text-base" onClick={onStart} disabled={start.isPending}>
          <PlayIcon className="fill-current" aria-hidden />
          {start.isPending ? "Iniciando…" : "Iniciar ruta"}
        </Button>
      ) : null}
      {start.isError ? <ErrorNote error={start.error} /> : null}

      {next ? <NextStopCard stop={next} total={progress.total} /> : null}

      {allDone ? (
        <motion.div
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.3, ease: EASE }}
          className="flex flex-col items-center gap-2 rounded-2xl border border-line bg-surface px-6 py-8 text-center shadow-card"
        >
          <AnimatedCheck />
          <p className="mt-1 text-lg font-semibold tracking-tight">Terminaste tus entregas</p>
          <p className="text-[13px] text-ink-2">
            <span className="num">{progress.delivered}</span> entregadas
            {progress.failed > 0 ? <> · <span className="num">{progress.failed}</span> sin entregar</> : null}
          </p>
        </motion.div>
      ) : null}

      {rest.length > 0 ? (
        <div className="flex flex-col gap-2">
          <h2 className="px-1 text-xs font-medium uppercase tracking-wide text-ink-2">
            {next ? "Después" : "Paradas"}
          </h2>
          <Stagger as="ol" aria-label="Paradas" className="relative flex flex-col">
            {rest.map((stop, i) => (
              <StopRow key={stop.id} stop={stop} first={i === 0} last={i === rest.length - 1} />
            ))}
          </Stagger>
        </div>
      ) : null}

      {inProgress ? <ReportIncident routeId={route.id} /> : null}
    </section>
  );
}

/** La parada protagonista: dirección grande, hora de llegada y un toque para navegar. */
function NextStopCard({ stop, total }: { stop: DriverStop; total: number }) {
  const nav = navigationUrl(stop);
  return (
    <motion.article
      aria-label="Próxima parada"
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.35, ease: EASE }}
      className="flex flex-col gap-5 rounded-2xl border border-line bg-surface p-5 shadow-lift"
    >
      <div className="flex items-center justify-between gap-3">
        <span className="inline-flex items-center gap-2 text-[13px] font-medium text-ink-3">
          <span className="live-dot size-2 rounded-full bg-delivery" aria-hidden />
          Próxima parada
        </span>
        <span className="num text-xs text-ink-2">{stop.sequence} de {total}</span>
      </div>

      <div className="flex flex-col gap-1.5">
        <h2 className="text-[26px] font-semibold leading-tight tracking-tight">{stop.recipient || stop.order_code}</h2>
        <p className="text-base leading-snug text-ink-3">{stop.address}</p>
      </div>

      <div className="flex items-baseline gap-2 border-t border-line pt-4">
        <span className="text-[13px] text-ink-2">Llegada estimada</span>
        <span className="num ml-auto text-[28px] font-medium leading-none tracking-tight">{formatClock(stop.eta)}</span>
      </div>

      <div className={cn("grid gap-2.5", nav ? "grid-cols-[1.4fr_1fr]" : "grid-cols-1")}>
        {/* Un toque para salir manejando: la navegación se queda dentro de enruta (RUT-78) */}
        {nav ? (
          <Button asChild className="h-14 rounded-xl text-base">
            <Link to={`/conductor/navegar/${stop.id}`}><NavigationIcon className="fill-current" aria-hidden /> Navegar</Link>
          </Button>
        ) : null}
        <Button asChild variant={nav ? "outline" : "default"} className="h-14 rounded-xl text-base">
          <Link to={`/conductor/paradas/${stop.id}`}>Llegué</Link>
        </Button>
      </div>
    </motion.article>
  );
}

/** Fila de la línea de tiempo: punto en el riel, destinatario, dirección y hora. */
function StopRow({ stop, first, last }: { stop: DriverStop; first: boolean; last: boolean }) {
  const delivered = stop.status === "delivered";
  const failed = stop.status === "failed";
  const marked = delivered || failed;
  return (
    <StaggerItem as="li" className="relative">
      {/* Riel vertical: no se pasa del primero ni del último punto */}
      <span
        className={cn("absolute left-[15px] w-px bg-line-strong", first ? "top-1/2" : "top-0", last ? "bottom-1/2" : "bottom-0")}
        aria-hidden
      />
      <Link
        to={`/conductor/paradas/${stop.id}`}
        className="group relative flex min-h-14 items-center gap-3 rounded-xl py-2 pr-2 transition-colors hover:bg-hover active:bg-hover"
      >
        <span
          className={cn(
            "z-10 flex size-[31px] shrink-0 items-center justify-center rounded-full border text-xs",
            delivered ? "border-ok bg-ok/10 text-ok" : failed ? "border-err bg-err/10 text-err" : "border-line-strong bg-surface text-ink-3",
          )}
        >
          {delivered ? (
            <CheckIcon className="size-4" aria-label="Entregado" />
          ) : failed ? (
            <XIcon className="size-4" aria-label="No entregado" />
          ) : (
            <span className="num">{stop.sequence}</span>
          )}
        </span>
        <span className="flex min-w-0 flex-1 flex-col">
          <span className={cn("truncate text-[15px]", marked ? "text-ink-2" : "font-medium text-ink")}>{stop.recipient || stop.order_code}</span>
          <span className="truncate text-[13px] text-ink-2">
            {failed && stop.reason ? `No entregado · ${stop.reason}` : stop.address}
          </span>
        </span>
        <span className="num text-xs text-ink-2">{formatClock(stop.delivered_at ?? stop.eta)}</span>
        <ChevronRightIcon className="size-4 shrink-0 text-ink-2 transition-transform group-hover:translate-x-0.5" aria-hidden />
      </Link>
    </StaggerItem>
  );
}
