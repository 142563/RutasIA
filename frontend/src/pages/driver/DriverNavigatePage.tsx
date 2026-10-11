import { useQueryClient } from "@tanstack/react-query";
import { ArrowLeftIcon, CrosshairIcon, EllipsisVerticalIcon, ExternalLinkIcon, PhoneIcon } from "lucide-react";
import { DropdownMenu } from "radix-ui";
import * as React from "react";
import { Link, useParams } from "react-router";
import { NetworkMap, type MapMarker, type MapPath } from "@/components/map/NetworkMap";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/misc";
import { Skeleton } from "@/components/ui/motion";
import { findStop, navigationUrl, nextStop, telUrl, useDriverRouteMap, useDriverToday, type DriverRoute, type DriverStop } from "@/lib/driver";
import { formatDistance, geometryPairs, haversineKm, minutesToStop, remainingCodes } from "@/lib/driverNav";
import { formatClock } from "@/lib/format";
import type { LatLng } from "@/lib/geo";
import type { GraphNode } from "@/lib/types";
import { AlternativeRouteNotice } from "./AlternativeRouteNotice";

interface Fix extends LatLng { speedKmh: number | null; at: number }

/** Posición del celular solo para mostrarla aquí (compartirla con despacho se autoriza en «Mi ruta»). */
function useMyPosition(): Fix | null {
  const [fix, setFix] = React.useState<Fix | null>(null);
  React.useEffect(() => {
    if (!navigator.geolocation) return;
    const id = navigator.geolocation.watchPosition(
      (p) => setFix({ lat: p.coords.latitude, lng: p.coords.longitude, speedKmh: p.coords.speed == null ? null : p.coords.speed * 3.6, at: p.timestamp }),
      () => undefined,
      { enableHighAccuracy: true, maximumAge: 5000, timeout: 20000 },
    );
    return () => navigator.geolocation.clearWatch(id);
  }, []);
  return fix;
}

/** Conductor · Navegación dentro de enruta (RUT-78): la ruta la decide nuestro Dijkstra / A*. */
export function DriverNavigatePage() {
  const params = useParams();
  const today = useDriverToday();
  const requested = params.stopId ? findStop(today.data, Number(params.stopId)) : null;
  const active = today.data?.routes.find((r) => r.status === "in_progress") ?? today.data?.routes.find((r) => r.status === "planned");
  const route: DriverRoute | undefined = requested?.route ?? active;
  const stop = requested?.stop.status === "pending" ? requested.stop : route ? nextStop(route) : undefined;

  return (
    <div className="fixed inset-0 z-30 mx-auto flex w-full max-w-[480px] flex-col bg-bg">
      <header className="flex h-14 shrink-0 items-center gap-1 border-b border-line bg-surface px-2">
        <Link to="/conductor" aria-label="Volver a mi ruta" className="inline-flex h-12 items-center gap-1.5 rounded-lg px-2 text-[15px] font-medium text-ink hover:bg-hover">
          <ArrowLeftIcon className="size-5" aria-hidden /> Mi ruta
        </Link>
        {stop ? <GoogleMapsMenu stop={stop} /> : null}
      </header>
      {today.isPending ? (
        <div className="flex flex-1 flex-col gap-3 p-4"><Skeleton className="flex-1 rounded-2xl" /><Skeleton className="h-40 rounded-2xl" /></div>
      ) : !route || !stop ? (
        <div className="flex flex-1 items-center p-4">
          <EmptyState title="No hay una parada pendiente">
            Cuando tengas una ruta con entregas por hacer, la navegación aparecerá aquí.
          </EmptyState>
        </div>
      ) : (
        <Navigation route={route} stop={stop} />
      )}
    </div>
  );
}

function GoogleMapsMenu({ stop }: { stop: DriverStop }) {
  const nav = navigationUrl(stop);
  if (!nav) return null;
  return (
    <DropdownMenu.Root>
      <DropdownMenu.Trigger asChild>
        <button type="button" aria-label="Más opciones" className="ml-auto flex size-12 items-center justify-center rounded-lg text-ink hover:bg-hover">
          <EllipsisVerticalIcon className="size-5" aria-hidden />
        </button>
      </DropdownMenu.Trigger>
      <DropdownMenu.Portal>
        <DropdownMenu.Content align="end" sideOffset={6} className="z-50 min-w-56 rounded-xl border border-line bg-elevated p-1.5 shadow-pop">
          <DropdownMenu.Item asChild>
            <a href={nav} target="_blank" rel="noopener noreferrer"
              className="flex h-12 cursor-pointer items-center gap-2.5 rounded-lg px-3 text-[15px] text-ink outline-none data-[highlighted]:bg-hover">
              <ExternalLinkIcon className="size-4" aria-hidden /> Abrir en Google Maps
            </a>
          </DropdownMenu.Item>
        </DropdownMenu.Content>
      </DropdownMenu.Portal>
    </DropdownMenu.Root>
  );
}

function Navigation({ route, stop }: { route: DriverRoute; stop: DriverStop }) {
  const client = useQueryClient();
  const routeMap = useDriverRouteMap(route.id);
  const fix = useMyPosition();
  const [follow, setFollow] = React.useState(true);

  const codes = React.useMemo(() => remainingCodes(routeMap.data, stop.sequence), [routeMap.data, stop.sequence]);
  const pairs = React.useMemo(() => geometryPairs(codes), [codes]);
  const nodes: GraphNode[] = React.useMemo(() => routeMap.data?.nodes ?? [], [routeMap.data]);

  // NetworkMap pide la geometría a /api/routing/geometry/ (solo despacho, RUT-86). Aquí se le entrega la de
  // ESTA ruta, que sí puede ver el conductor, en su misma caché y con la misma clave que usa el mapa.
  React.useEffect(() => {
    if (!routeMap.data || pairs.length === 0) return;
    const seed = () => client.setQueryData(["routing-geometry", pairs], routeMap.data!.edges);
    seed();
    const timer = window.setInterval(seed, 20_000);
    return () => window.clearInterval(timer);
  }, [client, routeMap.data, pairs]);

  const paths: MapPath[] = React.useMemo(
    () => (codes.length >= 2 ? [{ codes, color: "var(--color-accent)", width: 6, followRoads: true }] : []),
    [codes],
  );
  const markers: MapMarker[] = route.stops
    .filter((s) => s.status === "pending" && s.lat != null && s.lng != null)
    .map((s) => ({ id: `s${s.id}`, kind: "stop", label: String(s.sequence), lat: s.lat!, lng: s.lng! }));

  const target: LatLng | null = stop.lat != null && stop.lng != null ? { lat: stop.lat, lng: stop.lng } : null;
  const overview: LatLng[] = [...nodes.filter((n) => codes.includes(n.code)), ...markers];
  const fitRef = React.useRef<LatLng[]>([]);
  if (follow) fitRef.current = fix ? (target ? [fix, target] : [fix]) : overview;
  else if (fitRef.current.length === 0) fitRef.current = overview;

  const vehicles = fix ? [{ id: "yo", label: "Tú", position: { lat: fix.lat, lng: fix.lng, recorded_at: new Date(fix.at).toISOString() } }] : undefined;
  const distanceKm = fix && target ? haversineKm(fix, target) : null;
  const minutes = minutesToStop(fix, fix?.speedKmh ?? null, stop);
  const tel = telUrl(stop.phone);

  return (
    <>
      <div className="relative min-h-0 flex-1 [&>div>div:last-child]:hidden" onPointerDown={() => setFollow(false)}>
        <NetworkMap
          fill
          nodes={nodes}
          edges={[]}
          paths={paths}
          markers={markers}
          vehicles={vehicles}
          fitTo={fitRef.current.length ? fitRef.current : undefined}
          renderEdges={() => null}
          labels="none"
          ariaLabel="Mapa de tu ruta"
        />
        <div className="absolute inset-x-2 top-2 z-10 max-h-[75%] overflow-y-auto" onPointerDown={(e) => e.stopPropagation()}>
          <AlternativeRouteNotice route={route} />
        </div>
        {!follow ? (
          <Button onClick={() => setFollow(true)} className="absolute bottom-3 left-3 z-10 h-12 rounded-full px-5 text-[15px] shadow-lift">
            <CrosshairIcon aria-hidden /> Recentrar
          </Button>
        ) : null}
        {routeMap.isError ? (
          <p className="absolute bottom-3 right-3 z-10 max-w-[60%] rounded-lg border border-line bg-surface px-3 py-2 text-[13px] text-ink-3">
            No se pudo cargar el trazo de tu ruta. Puedes seguir con la parada.
          </p>
        ) : null}
      </div>

      <section aria-label="Siguiente parada" className="shrink-0 border-t border-line bg-surface px-4 pb-[max(1rem,env(safe-area-inset-bottom))] pt-4 shadow-lift">
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0">
            <p className="text-[13px] font-medium text-ink-2">Parada <span className="num">{stop.sequence}</span> de <span className="num">{route.stops.length}</span></p>
            <h1 className="truncate text-[22px] font-semibold leading-tight tracking-tight">{stop.recipient || stop.order_code}</h1>
            <p className="line-clamp-2 text-[15px] leading-snug text-ink-3">{stop.address}</p>
            {stop.reference ? <p className="line-clamp-1 text-[13px] text-ink-2">Ref.: {stop.reference}</p> : null}
          </div>
          <div className="shrink-0 text-right" aria-live="polite">
            <p className="num text-[26px] font-semibold leading-none tracking-tight">{minutes != null ? `${minutes} min` : "—"}</p>
            <p className="num mt-1 text-[13px] text-ink-2">
              {distanceKm != null ? `${formatDistance(distanceKm)} · ` : ""}{formatClock(stop.eta)}
            </p>
          </div>
        </div>
        <div className="mt-3 flex gap-2.5">
          <Button asChild className="h-14 flex-1 rounded-xl text-lg font-semibold">
            <Link to={`/conductor/paradas/${stop.id}`}>Llegué</Link>
          </Button>
          {tel ? (
            <Button asChild variant="outline" className="size-14 shrink-0 rounded-xl p-0">
              <a href={tel} aria-label={`Llamar a ${stop.recipient || "el cliente"}`}><PhoneIcon className="size-5" aria-hidden /></a>
            </Button>
          ) : null}
        </div>
      </section>
    </>
  );
}
