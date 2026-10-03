import { ArrowRightIcon, ClockIcon, PackageIcon, PencilIcon } from "lucide-react";
import * as React from "react";
import { Link, useNavigate, useSearchParams } from "react-router";
import { toast } from "sonner";
import { DataSourceNote } from "@/components/DataSourceNote";
import { NetworkMap, type MapMarker } from "@/components/map/NetworkMap";
import { Button } from "@/components/ui/button";
import { Field, Input, Select } from "@/components/ui/field";
import { EmptyState, ErrorNote, Metric, PageHeader, Segmented, Spinner } from "@/components/ui/misc";
import { formatClock, formatKm, formatMinutes, toLocalInputValue } from "@/lib/format";
import { useDepots, useOrders } from "@/lib/orders";
import { routeNodes, useCreateRoute, useFleet, usePlan, type Criterion, type PlanResponse, type PlanVariant } from "@/lib/planning";
import { useNetwork } from "@/lib/queries";
import { bandLabel } from "@/lib/traffic";
import type { GraphEdge, GraphNode } from "@/lib/types";
import { cn } from "@/lib/utils";
import { groupByZone, placesLabel } from "@/lib/zones";

const ROUTE_COLOR = "#2f4bd8";
const OTHER_COLOR = "#9a9ca1";

function defaultDeparture(): string {
  // Próximo cuarto de hora, en hora de Guatemala
  const now = new Date();
  now.setMinutes(Math.ceil(now.getMinutes() / 15) * 15, 0, 0);
  return toLocalInputValue(now);
}

function parseIds(value: string | null): number[] {
  return (value ?? "").split(",").map(Number).filter((n) => Number.isInteger(n) && n > 0);
}

export function PlannerPage() {
  const [params, setParams] = useSearchParams();
  const navigate = useNavigate();
  const ids = React.useMemo(() => parseIds(params.get("pedidos")), [params]);
  const [editing, setEditing] = React.useState(ids.length === 0);
  const [pickMode, setPickMode] = React.useState<"zones" | "list">("zones");
  const [departure, setDeparture] = React.useState(defaultDeparture);
  const [returnToDepot, setReturnToDepot] = React.useState(true);
  const [allowUnpaved, setAllowUnpaved] = React.useState(false);
  const [serviceMin, setServiceMin] = React.useState(10);
  const [criterion, setCriterion] = React.useState<Criterion>("time");
  const [driverId, setDriverId] = React.useState("");
  const [vehicleId, setVehicleId] = React.useState("");

  const network = useNetwork();
  const depots = useDepots();
  const depotId = depots.data?.depots[0]?.id;
  const request = depotId && ids.length && departure
    ? { depot_id: depotId, order_ids: ids, departure, service_min: serviceMin, return_to_depot: returnToDepot, allow_unpaved: allowUnpaved }
    : null;
  const plan = usePlan(request);
  const fleet = useFleet();
  const create = useCreateRoute();

  const setIds = (next: number[]) => {
    const p = new URLSearchParams(params);
    if (next.length) p.set("pedidos", next.join(","));
    else p.delete("pedidos");
    setParams(p, { replace: true });
  };

  const data = plan.data;
  const variant = data ? (criterion === "time" ? data.fastest : data.shortest) : null;
  const other = data ? (criterion === "time" ? data.shortest : data.fastest) : null;
  const vehicle = fleet.vehicles.find((v) => String(v.id) === vehicleId);
  const overCapacity = !!(vehicle && data && data.total_weight_kg > vehicle.capacity_kg);
  const showPicker = editing || ids.length === 0;

  // Sugerencia: el vehículo más pequeño donde cabe la carga, con su conductor.
  // Se recalcula con cada carga nueva, salvo que el despachador ya haya elegido a mano.
  const manualPick = React.useRef(false);
  const idsKey = ids.join(",");
  React.useEffect(() => { manualPick.current = false; }, [idsKey]);
  const weight = data?.total_weight_kg;
  React.useEffect(() => {
    if (weight === undefined || manualPick.current) return;
    const fits = fleet.vehicles
      .filter((v) => v.is_active && v.capacity_kg >= weight)
      .sort((a, b) => a.capacity_kg - b.capacity_kg)[0];
    setVehicleId(fits ? String(fits.id) : "");
    setDriverId(fits?.driver_id ? String(fits.driver_id) : "");
    // fleet.vehicles es un arreglo nuevo en cada render: basta con saber cuándo llegan
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [weight, fleet.vehicles.length]);

  function confirm() {
    if (!request) return;
    create.mutate(
      { ...request, criterion, driver_id: driverId ? Number(driverId) : undefined, vehicle_id: vehicleId ? Number(vehicleId) : undefined },
      {
        onSuccess: ({ route }) => {
          toast.success(`Ruta ${route.code} asignada`, { description: `${formatMinutes(route.driving_minutes)} de manejo con tráfico. Sigue su avance aquí.` });
          navigate("/");
        },
      },
    );
  }

  const depotName = depots.data?.depots[0]?.name ?? "Bodega";
  const subtitle = `Salida ${departure.slice(11, 16)} · ${depotName}${data ? ` · ${data.band_label}` : ""}`;

  return (
    <div className="flex min-h-full flex-col">
      <PageHeader
        title="Planificar ruta"
        subtitle={subtitle}
        actions={data ? (
          <Segmented label="Criterio" value={criterion} onChange={setCriterion}
            options={[{ value: "distance", label: "Más corta" }, { value: "time", label: "Más rápida" }]} />
        ) : null}
      />
      <div className="grid flex-1 lg:grid-cols-[minmax(0,440px)_minmax(0,1fr)]">
        <section className="flex flex-col gap-6 border-line px-6 py-6 lg:border-r lg:px-8">
          {/* La hora de salida importa: el tráfico cambia según la franja */}
          <Field label="Hora de salida" htmlFor="departure" hint="El tráfico cambia según la hora: prueba distintas.">
            <Input id="departure" type="datetime-local" className="num" value={departure} onChange={(e) => setDeparture(e.target.value)} />
          </Field>

          {showPicker ? (
            pickMode === "zones"
              ? <ZonePicker onPick={(zoneIds) => { setIds(zoneIds); setEditing(false); }} onList={() => setPickMode("list")} />
              : <OrderPicker selected={ids} onChange={setIds} onDone={() => setEditing(false)} onZones={() => setPickMode("zones")} />
          ) : null}

          <details className="group text-[13px]">
            <summary className="cursor-pointer list-none text-ink-2 hover:text-ink">Más opciones</summary>
            <div className="mt-3 grid grid-cols-2 gap-3">
              <Field label="Minutos por entrega" htmlFor="service">
                <Input id="service" type="number" min={0} max={120} className="num" value={serviceMin}
                  onChange={(e) => setServiceMin(Math.max(0, Math.min(120, Number(e.target.value) || 0)))} />
              </Field>
              <label className="col-span-2 flex items-center gap-2 text-ink-3">
                <input type="checkbox" className="size-4 accent-ink" checked={returnToDepot} onChange={(e) => setReturnToDepot(e.target.checked)} />
                Regresar a la bodega al terminar
              </label>
              <label className="col-span-2 flex items-center gap-2 text-ink-3">
                <input type="checkbox" className="size-4 accent-ink" checked={allowUnpaved} onChange={(e) => setAllowUnpaved(e.target.checked)} />
                Permitir caminos de terracería (por defecto se evitan)
              </label>
            </div>
          </details>

          {plan.isFetching && !data ? <Spinner label="Calculando rutas…" /> : null}
          {plan.error ? <ErrorNote error={plan.error} /> : null}

          {data && variant && other && !showPicker ? (
            <>
              <PlanSummary data={data} variant={variant} criterion={criterion} fetching={plan.isFetching} />
              <DepartureOptions data={data} current={data.fastest.driving_minutes} onPick={(iso) => setDeparture(iso.slice(0, 16))} />
              <StopList variant={variant} returnToDepot={data.return_to_depot} depotName={data.depot.name}
                onEdit={() => { setPickMode("zones"); setEditing(true); }} />

              <div className="flex flex-col gap-3 border-t border-line pt-5">
                <h2 className="text-sm font-semibold">Asignar <span className="font-normal text-ink-2">· sugerido según la carga</span></h2>
                <div className="grid grid-cols-2 gap-3">
                  <Field label="Conductor" htmlFor="driver">
                    <Select id="driver" value={driverId} onChange={(e) => { manualPick.current = true; setDriverId(e.target.value); }}>
                      <option value="">Sin asignar</option>
                      {fleet.drivers.map((d) => <option key={d.id} value={d.id}>{d.name}</option>)}
                    </Select>
                  </Field>
                  <Field label="Vehículo" htmlFor="vehicle" error={overCapacity ? `La carga (${data.total_weight_kg} kg) excede la capacidad.` : null}>
                    <Select id="vehicle" value={vehicleId} onChange={(e) => { manualPick.current = true; setVehicleId(e.target.value); }}>
                      <option value="">Sin asignar</option>
                      {fleet.vehicles.map((v) => <option key={v.id} value={v.id}>{v.plate} · {v.capacity_kg.toLocaleString("es-GT")} kg</option>)}
                    </Select>
                  </Field>
                </div>
                {create.error ? <ErrorNote error={create.error} /> : null}
                <div className="flex gap-2">
                  <Button size="lg" className="flex-1" disabled={create.isPending || overCapacity || plan.isFetching} onClick={confirm}>
                    {create.isPending ? "Asignando…" : "Confirmar y asignar"}
                  </Button>
                  <Button size="lg" variant="outline" onClick={() => { setPickMode("list"); setEditing(true); }}>Ajustar</Button>
                </div>
              </div>
              <DataSourceNote source={data.data_source} />
            </>
          ) : null}
        </section>

        <section aria-label="Mapa de la ruta" className="relative bg-surface p-3 lg:sticky lg:top-0 lg:h-screen">
          {network.data ? (
            <RouteMap nodes={network.data.nodes} edges={network.data.edges} data={data} variant={variant} other={other} />
          ) : (
            <div className="p-6"><Spinner label="Cargando mapa…" /></div>
          )}
        </section>
      </div>
    </div>
  );

}

function RouteMap({ nodes, edges, data, variant, other }: {
nodes: GraphNode[];
edges: GraphEdge[];
data?: PlanResponse;
variant: PlanVariant | null;
other: PlanVariant | null;
}) {
  const markers: MapMarker[] = [];
  if (data) {
    markers.push({ id: "depot", kind: "depot", lat: data.depot.lat, lng: data.depot.lng, label: data.depot.name });
    variant?.stops.forEach((s) => markers.push({ id: `s${s.order_id}`, kind: "stop", lat: s.lat, lng: s.lng, label: String(s.sequence) }));
  }
  return (
    <div className="flex h-[70vh] flex-col lg:h-full">
      <NetworkMap
        nodes={nodes}
        edges={edges}
        fitTo={markers.length ? [...markers, ...(variant ? routeNodes(variant) : []).map((c) => nodes.find((n) => n.code === c)!).filter(Boolean)] : undefined}
        fill
        paths={[
          ...(other && variant && routeNodes(other).join() !== routeNodes(variant).join()
            ? [{ codes: routeNodes(other), color: OTHER_COLOR, width: 2.5, dashed: true }] : []),
          ...(variant ? [{ codes: routeNodes(variant), color: ROUTE_COLOR, width: 4, followRoads: true }] : []),
        ]}
        markers={markers}
      />
      {variant && other ? (
        <div className="flex flex-wrap gap-4 px-2 pt-2 text-xs text-ink-2">
          <span className="flex items-center gap-1.5"><span className="h-1 w-5 rounded" style={{ background: ROUTE_COLOR }} /> Ruta elegida</span>
          <span className="flex items-center gap-1.5"><span className="h-0.5 w-5 border-t-2 border-dashed" style={{ borderColor: OTHER_COLOR }} /> La otra opción</span>
          <span className="flex items-center gap-1.5"><span className="size-2.5 rounded-sm bg-ink" /> Bodega</span>
        </div>
      ) : null}
    </div>
  );
}

function unpavedKm(variant: PlanVariant) {
  return variant.legs.reduce((sum, leg) => sum + (leg.unpaved_km ?? 0), 0);
}

function PlanSummary({ data, variant, criterion, fetching }: { data: PlanResponse; variant: PlanVariant; criterion: Criterion; fetching: boolean }) {
  const saved = data.minutes_saved;
  const hint = criterion === "time"
    ? saved >= 1 ? `${formatMinutes(saved)} menos que la ruta más corta` : "Igual que la ruta más corta con este tráfico"
    : saved >= 1 ? `${formatMinutes(saved)} más que la más rápida` : "Coincide con la más rápida";
  return (
    <div className={cn("flex flex-col gap-5 transition-opacity", fetching && "opacity-60")}>
      <Metric label="Tiempo total de manejo" value={formatMinutes(variant.driving_minutes)} hint={
        <span className={cn(criterion === "time" && saved >= 1 && "font-medium text-ok")}>{hint}</span>} />
      <div className="grid grid-cols-3 gap-4 border-b border-line pb-5">
        <Metric label="Distancia" value={formatKm(variant.total_km)} className="[&>span:nth-child(2)]:text-lg" />
        <Metric label="Paradas" value={variant.stops.length} className="[&>span:nth-child(2)]:text-lg" />
        <Metric label={data.return_to_depot ? "Regreso" : "Termina"} value={formatClock(variant.finish_at)} className="[&>span:nth-child(2)]:text-lg" />
      </div>
      {unpavedKm(variant) >= 1 ? (
        <p className="rounded-lg bg-warn/10 px-3 py-2 text-[13px] text-warn">
          Incluye {formatKm(unpavedKm(variant))} de terracería: no hay otra carretera hacia alguna parada o se permitió usarla.
        </p>
      ) : null}
      <details className="text-xs text-ink-2">
        <summary className="cursor-pointer list-none hover:text-ink">¿Cómo lo calculó?</summary>
        <p className="mt-2 leading-relaxed">
          Primero Dijkstra mide el tiempo entre todas las paradas con el tráfico de la hora de salida. Luego se
          ordenan las entregas (vecino más cercano + 2-opt) y A* busca el camino de cada tramo ·{" "}
          <span className="num">{variant.expanded.toLocaleString("es-GT")}</span> nodos revisados.
        </p>
      </details>
    </div>
  );
}

function DepartureOptions({ data, current, onPick }: { data: PlanResponse; current: number; onPick: (iso: string) => void }) {
  const options = data.departure_options;
  const best = options.reduce((a, b) => (b.driving_minutes < a.driving_minutes ? b : a));
  const max = Math.max(...options.map((o) => o.driving_minutes));
  const min = Math.min(...options.map((o) => o.driving_minutes));
  const gain = current - best.driving_minutes;
  return (
    <details className="group border-b border-line pb-5" open={gain >= 10}>
      <summary className="flex cursor-pointer list-none items-center gap-2 text-sm">
        <ClockIcon className="size-4 text-ink-2" />
        {gain >= 1
          ? <span>Si sales a las <b className="num">{formatClock(best.departure)}</b> ({best.band_label.toLowerCase()}) ahorras <b className="num text-ok">{formatMinutes(gain)}</b></span>
          : <span>Ya sales en una de las mejores franjas del día</span>}
      </summary>
      <ul className="mt-3 flex flex-col gap-1.5" aria-label="Tiempo de manejo según la hora de salida">
        {options.map((o) => {
          const width = max === min ? 100 : 35 + 65 * ((o.driving_minutes - min) / (max - min));
          const isBest = o.band === best.band;
          const isCurrent = o.band === data.band;
          return (
            <li key={o.band}>
              <button type="button" onClick={() => onPick(o.departure)} className="group/row flex w-full items-center gap-3 rounded-md px-1 py-0.5 text-left text-xs hover:bg-hover">
                <span className="w-24 shrink-0 text-ink-3">{bandLabel(o.band)}</span>
                <span className="num w-10 shrink-0 text-ink-2">{formatClock(o.departure)}</span>
                <span className="relative h-2 flex-1 rounded-full bg-hover">
                  <span className="absolute inset-y-0 left-0 rounded-full" style={{ width: `${width}%`, background: isBest ? "#1a7f4b" : isCurrent ? "#111113" : "#c9cac5" }} />
                </span>
                <span className={cn("num w-20 shrink-0 text-right", isBest ? "font-medium text-ok" : "text-ink-3")}>{formatMinutes(o.driving_minutes)}</span>
              </button>
            </li>
          );
        })}
      </ul>
      <p className="mt-2 text-xs text-ink-2">Toca una franja para usar esa hora de salida.</p>
    </details>
  );
}

function StopList({ variant, returnToDepot, depotName, onEdit }: { variant: PlanVariant; returnToDepot: boolean; depotName: string; onEdit: () => void }) {
  return (
    <div className="flex flex-col">
      <div className="mb-2 flex items-center justify-between">
        <h2 className="text-sm font-semibold">Paradas en orden</h2>
        <Button variant="ghost" size="sm" onClick={onEdit}><PencilIcon /> Cambiar pedidos</Button>
      </div>
      <ol className="flex flex-col">
        {variant.stops.map((stop, i) => {
          const leg = variant.legs[i];
          return (
            <li key={stop.order_id} className="flex gap-3 border-b border-line py-3 last:border-b-0">
              <span className="num grid size-6 shrink-0 place-items-center rounded-full bg-ink text-[11px] font-semibold text-white">{stop.sequence}</span>
              <div className="min-w-0 flex-1">
                <div className="flex items-baseline justify-between gap-2">
                  <p className="truncate text-sm font-medium">{stop.recipient}</p>
                  <span className="num shrink-0 text-sm">{formatClock(stop.eta)}</span>
                </div>
                <p className="truncate text-xs text-ink-2">{stop.node?.name} · {stop.address}</p>
                {leg ? (
                  <p className="num mt-1 text-[11px] text-ink-2">
                    +{formatMinutes(leg.minutes)} · {formatKm(leg.km)}{leg.roads.length ? ` · ${leg.roads.join(" → ")}` : ""} · {bandLabel(leg.band)}
                  </p>
                ) : null}
              </div>
            </li>
          );
        })}
        {returnToDepot && variant.legs.length > variant.stops.length ? (
          <li className="flex gap-3 py-3 text-xs text-ink-2">
            <span className="grid size-6 shrink-0 place-items-center"><span className="size-2.5 rounded-sm bg-ink" /></span>
            <span className="flex-1">Regreso a {depotName}</span>
            <span className="num">{formatClock(variant.finish_at)}</span>
          </li>
        ) : null}
      </ol>
    </div>
  );
}

function ZonePicker({ onPick, onList }: { onPick: (ids: number[]) => void; onList: () => void }) {
  const pending = useOrders({ status: "pending" });
  const zones = groupByZone(pending.data?.orders ?? []);
  return (
    <div className="flex flex-col gap-3">
      <div>
        <h2 className="text-sm font-semibold">¿Qué zona vas a entregar?</h2>
        <p className="text-[13px] text-ink-2">Los pedidos pendientes, agrupados por región. Elige una y la ruta sale sola.</p>
      </div>
      {pending.isPending ? <Spinner /> : null}
      {pending.data && zones.length === 0 ? (
        <EmptyState icon={<PackageIcon />} title="No hay pedidos pendientes"
          action={<Button asChild variant="outline"><Link to="/pedidos">Ir a Pedidos</Link></Button>}>
          Registra un pedido y vuelve aquí para planificar su ruta.
        </EmptyState>
      ) : null}
      <ul className="flex flex-col gap-2">
        {zones.map((z) => (
          <li key={z.code}>
            <button type="button" onClick={() => onPick(z.orderIds)}
              className="group flex w-full items-center gap-3 rounded-lg border border-line bg-surface px-4 py-3 text-left transition-colors hover:border-ink">
              <span className="min-w-0 flex-1">
                <span className="block text-sm font-medium">{z.name}</span>
                <span className="block truncate text-xs text-ink-2">{placesLabel(z.places)}</span>
              </span>
              <span className="num shrink-0 text-right text-xs text-ink-2">
                <span className="block text-sm font-medium text-ink">{z.orderIds.length} {z.orderIds.length === 1 ? "pedido" : "pedidos"}</span>
                {z.weightKg.toLocaleString("es-GT", { maximumFractionDigits: 1 })} kg
              </span>
              <ArrowRightIcon className="size-4 shrink-0 text-ink-2 transition-transform group-hover:translate-x-0.5 group-hover:text-ink" />
            </button>
          </li>
        ))}
      </ul>
      {zones.length > 0 ? (
        <button type="button" onClick={onList} className="self-start text-[13px] text-ink-2 underline hover:text-ink">
          Prefiero elegir los pedidos uno por uno
        </button>
      ) : null}
    </div>
  );
}

function OrderPicker({ selected, onChange, onDone, onZones }: {
  selected: number[]; onChange: (ids: number[]) => void; onDone: () => void; onZones: () => void;
}) {
  const pending = useOrders({ status: "pending" });
  const set = new Set(selected);
  const orders = pending.data?.orders ?? [];
  return (
    <div className="flex flex-col gap-3">
      <div className="flex items-center justify-between">
        <h2 className="text-sm font-semibold">Pedidos pendientes <span className="num font-normal text-ink-2">{set.size}/{orders.length}</span></h2>
        <div className="flex gap-2">
          <Button size="sm" variant="ghost" onClick={onZones}>Por zonas</Button>
          <Button size="sm" onClick={onDone} disabled={set.size === 0}>Calcular ruta</Button>
        </div>
      </div>
      {pending.isPending ? <Spinner /> : null}
      {pending.data && orders.length === 0 ? <p className="text-[13px] text-ink-2">No hay pedidos pendientes.</p> : null}
      <ul className="max-h-[420px] overflow-y-auto rounded-lg border border-line">
        {orders.map((o) => (
          <li key={o.id} className="border-b border-line last:border-b-0">
            <label className="flex cursor-pointer items-center gap-3 px-3 py-2 hover:bg-hover/60">
              <input type="checkbox" className="size-4 accent-ink" checked={set.has(o.id)}
                onChange={() => onChange(set.has(o.id) ? selected.filter((id) => id !== o.id) : [...selected, o.id])} />
              <span className="min-w-0 flex-1">
                <span className="block truncate text-sm">{o.recipient}</span>
                <span className="block text-xs text-ink-2">{o.node?.name}</span>
              </span>
              <span className="num text-xs text-ink-2">{o.weight_kg} kg</span>
            </label>
          </li>
        ))}
      </ul>
    </div>
  );
}
