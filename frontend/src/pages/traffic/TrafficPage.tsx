import { useQuery } from "@tanstack/react-query";
import * as React from "react";
import { CartesianGrid, Line, LineChart, ReferenceDot, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { DataSourceNote } from "@/components/DataSourceNote";
import { NetworkMap } from "@/components/map/NetworkMap";
import { NodeSearch } from "@/components/NodeSearch";
import { Field } from "@/components/ui/field";
import { ErrorNote, Metric, PageHeader, Segmented, Spinner } from "@/components/ui/misc";
import { api } from "@/lib/api";
import { CONGESTION_STEPS, congestionColor } from "@/lib/congestion";
import { formatMinutes } from "@/lib/format";
import { useNetwork } from "@/lib/queries";
import { BANDS, bandFor, dayTypeFor, type Band, type DayType } from "@/lib/traffic";
import type { DataSource, GraphNode } from "@/lib/types";

interface ProfileEdge {
  from: string;
  to: string;
  road: string;
  t0_min: number;
  multiplier: number;
}
interface ProfileResponse {
  band: Band;
  day_type: DayType;
  calibrated: boolean;
  edges: ProfileEdge[];
  data_source: DataSource;
}
interface BestDepartureResponse {
  bands: { band: Band; band_label: string; departure: string; minutes: number; roads: string[] }[];
  best_band: Band;
  day_type: DayType;
}

// Zona metropolitana: donde se nota la asimetría de los picos (entrar vs salir de la capital)
const METRO = [
  { lat: 14.36, lng: -90.9 },
  { lat: 14.8, lng: -90.35 },
];

export function TrafficPage() {
  const network = useNetwork();
  const now = new Date();
  const [bandIndex, setBandIndex] = React.useState(BANDS.findIndex((b) => b.id === bandFor(now)));
  const [dayType, setDayType] = React.useState<DayType>(dayTypeFor(now));
  const [view, setView] = React.useState<"pais" | "metro">("metro");
  const band = BANDS[bandIndex];

  const profile = useQuery({
    queryKey: ["traffic-profile", band.id, dayType],
    queryFn: () => api<ProfileResponse>("/api/traffic/profile/", { query: { band: band.id, day: dayType } }),
    placeholderData: (previous) => previous,
  });

  const names = React.useMemo(() => new Map(network.data?.nodes.map((n) => [n.code, n.name]) ?? []), [network.data]);
  const edges = profile.data?.edges ?? [];
  const stats = React.useMemo(() => {
    if (!edges.length) return null;
    const ms = edges.map((e) => e.multiplier);
    const mean = ms.reduce((a, b) => a + b, 0) / ms.length;
    const heavy = ms.filter((m) => m >= 1.5).length;
    const top = [...edges].sort((a, b) => b.multiplier - a.multiplier).slice(0, 5);
    return { mean, heavy, top };
  }, [edges]);

  return (
    <div className="flex min-h-full flex-col">
      <PageHeader title="Tráfico por franja" subtitle="Multiplicador m de cada tramo, en cada sentido: tiempo con tráfico = t0 × m." />
      <div className="flex flex-wrap items-end gap-x-6 gap-y-3 border-b border-line px-6 py-4 lg:px-8">
        <div className="flex min-w-[280px] flex-1 flex-col gap-1.5">
          <label htmlFor="band-slider" className="text-[13px] font-medium text-ink-3">
            Franja: <span className="text-ink">{band.label}</span> <span className="num text-ink-2">{band.hours}</span>
          </label>
          <input id="band-slider" type="range" min={0} max={BANDS.length - 1} step={1} value={bandIndex}
            onChange={(e) => setBandIndex(Number(e.target.value))} className="w-full accent-ink"
            aria-valuetext={`${band.label}, ${band.hours}`} />
          <div className="flex justify-between text-[11px] text-ink-2">
            {BANDS.map((b, i) => (
              <button key={b.id} type="button" onClick={() => setBandIndex(i)} className={i === bandIndex ? "font-medium text-ink" : "hover:text-ink"}>
                {b.label.replace("Media mañana", "Media m.").replace("Pico ", "P. ")}
              </button>
            ))}
          </div>
        </div>
        <Segmented label="Tipo de día" value={dayType} onChange={setDayType}
          options={[{ value: "weekday", label: "Laboral" }, { value: "weekend", label: "Fin de semana" }]} />
        <Segmented label="Vista" value={view} onChange={setView}
          options={[{ value: "metro", label: "Zona metropolitana" }, { value: "pais", label: "Todo el país" }]} />
      </div>

      <div className="grid flex-1 lg:grid-cols-[minmax(0,1fr)_minmax(0,380px)]">
        <section aria-label="Mapa de tráfico" className="border-line bg-surface p-3 lg:border-r">
          {profile.error ? <ErrorNote error={profile.error} /> : null}
          {network.data && profile.data ? (
            <>
              <NetworkMap
                nodes={network.data.nodes}
                edges={network.data.edges}
                fitTo={view === "metro" ? METRO : undefined}
                labels={view === "metro" ? "none" : "cabeceras"}
                renderEdges={(toXY) => (
                  <g strokeLinecap="round">
                    {edges.map((e) => {
                      const a = network.data!.nodes.find((n) => n.code === e.from);
                      const b = network.data!.nodes.find((n) => n.code === e.to);
                      if (!a || !b) return null;
                      const [x1, y1] = toXY(a);
                      const [x2, y2] = toXY(b);
                      // Cada sentido se dibuja desplazado a su derecha (se maneja por la derecha)
                      const len = Math.hypot(x2 - x1, y2 - y1) || 1;
                      const off = view === "metro" ? 3.2 : 1.8;
                      const ox = (-(y2 - y1) / len) * off;
                      const oy = ((x2 - x1) / len) * off;
                      return (
                        <line key={`${e.from}>${e.to}`} x1={x1 - ox} y1={y1 - oy} x2={x2 - ox} y2={y2 - oy}
                          stroke={congestionColor(e.multiplier)} strokeWidth={view === "metro" ? 5 : 3}>
                          <title>{`${names.get(e.from)} → ${names.get(e.to)} · ×${e.multiplier.toFixed(2)} · ${formatMinutes(e.t0_min)} sin tráfico → ${formatMinutes(e.t0_min * e.multiplier)}`}</title>
                        </line>
                      );
                    })}
                  </g>
                )}
              >
                {view === "metro"
                  ? (toXY) => (
                    <g fontSize={11} fill="#56595f" style={{ paintOrder: "stroke" }} stroke="#fff" strokeWidth={3}>
                      {network.data!.nodes.filter((n) => n.lat > METRO[0].lat && n.lat < METRO[1].lat && n.lng > METRO[0].lng && n.lng < METRO[1].lng)
                        .map((n) => { const [x, y] = toXY(n); return <text key={n.code} x={x + 6} y={y - 6}>{n.name.split(" (")[0]}</text>; })}
                    </g>
                  )
                  : undefined}
              </NetworkMap>
              <ul className="flex flex-wrap gap-x-4 gap-y-1 px-2 pt-2 text-xs text-ink-2" aria-label="Leyenda de congestión">
                {CONGESTION_STEPS.map((s) => (
                  <li key={s.min} className="flex items-center gap-1.5"><span className="h-1.5 w-5 rounded" style={{ background: s.color }} />{s.label}</li>
                ))}
              </ul>
              <p className="px-2 pt-1 text-xs text-ink-2">Cada tramo tiene dos líneas: una por sentido. Pasa el cursor sobre una para ver los minutos.</p>
            </>
          ) : (
            <div className="p-6"><Spinner label="Cargando tráfico…" /></div>
          )}
        </section>

        <aside className="flex flex-col gap-6 px-6 py-6 lg:px-8">
          {stats ? (
            <>
              <div className="grid grid-cols-2 gap-4">
                <Metric label="Multiplicador promedio" value={`×${stats.mean.toFixed(2)}`} />
                <Metric label="Tramos con tránsito pesado" value={stats.heavy} hint="m ≥ 1.5" />
              </div>
              <div>
                <h2 className="mb-2 text-sm font-semibold">Tramos más congestionados</h2>
                <ol className="flex flex-col">
                  {stats.top.map((e) => (
                    <li key={`${e.from}>${e.to}`} className="flex items-center justify-between gap-3 border-b border-line py-2 text-[13px] last:border-b-0">
                      <span className="min-w-0 truncate">{names.get(e.from)} → {names.get(e.to)}</span>
                      <span className="num shrink-0 font-medium" style={{ color: e.multiplier >= 1.5 ? "#9c3f16" : undefined }}>×{e.multiplier.toFixed(2)}</span>
                    </li>
                  ))}
                </ol>
              </div>
            </>
          ) : null}
          {profile.data && !profile.data.calibrated ? <p className="text-[13px] text-ink-2">Esta franja aún no está calibrada: se usa m = 1.</p> : null}
          <DataSourceNote source={profile.data?.data_source} />
        </aside>
      </div>

      {network.data ? <BestDeparture nodes={network.data.nodes} /> : null}
    </div>
  );
}

function BestDeparture({ nodes }: { nodes: GraphNode[] }) {
  const [origin, setOrigin] = React.useState(nodes.find((n) => n.code === "ciudad-guatemala")!);
  const [destination, setDestination] = React.useState(nodes.find((n) => n.code === "quetzaltenango")!);
  const [date, setDate] = React.useState(() => new Date(Date.now() - 6 * 3600 * 1000).toISOString().slice(0, 10));
  const query = useQuery({
    queryKey: ["best-departure", origin?.code, destination?.code, date],
    queryFn: () => api<BestDepartureResponse>("/api/routing/best-departure/", { query: { origin: origin.code, destination: destination.code, date } }),
    enabled: !!origin && !!destination && origin.code !== destination.code,
    placeholderData: (previous) => previous,
  });
  const data = query.data?.bands.map((b) => ({ ...b, label: BANDS.find((x) => x.id === b.band)?.label ?? b.band }));
  const best = data?.find((b) => b.band === query.data?.best_band);
  const worst = data?.reduce((a, b) => (b.minutes > a.minutes ? b : a));

  return (
    <section className="border-t border-line px-6 py-6 lg:px-8" aria-labelledby="best-title">
      <h2 id="best-title" className="text-base font-semibold">¿A qué hora conviene salir?</h2>
      <p className="mt-1 text-[13px] text-ink-2">Tiempo del mismo viaje saliendo a la hora representativa de cada franja.</p>
      <div className="mt-4 flex flex-wrap items-end gap-3">
        <Field label="Origen" htmlFor="bd-origin" className="w-full sm:w-52">
          <NodeSearch id="bd-origin" nodes={nodes} placeholder={origin.name} onSelect={setOrigin} />
        </Field>
        <Field label="Destino" htmlFor="bd-destination" className="w-full sm:w-52">
          <NodeSearch id="bd-destination" nodes={nodes} placeholder={destination.name} onSelect={setDestination} />
        </Field>
        <Field label="Fecha" htmlFor="bd-date">
          <input id="bd-date" type="date" value={date} onChange={(e) => setDate(e.target.value)}
            className="num h-9 rounded-lg border border-line-strong bg-surface px-3 text-sm" />
        </Field>
      </div>
      {query.error ? <div className="mt-4"><ErrorNote error={query.error} /></div> : null}
      {data && best && worst ? (
        <>
          <p className="mt-4 text-sm">
            Mejor salida: <b>{best.label}</b> ({formatMinutes(best.minutes)}). En {worst.label.toLowerCase()} tardarías{" "}
            <b className="num">{formatMinutes(worst.minutes - best.minutes)}</b> más.
          </p>
          <div className="mt-3 h-64 w-full max-w-4xl" role="img" aria-label={`Minutos de viaje por franja: ${data.map((d) => `${d.label} ${Math.round(d.minutes)}`).join(", ")}`}>
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={data} margin={{ top: 16, right: 24, bottom: 4, left: 4 }}>
                <CartesianGrid stroke="#ecece9" vertical={false} />
                <XAxis dataKey="label" tick={{ fontSize: 11, fill: "#6b6f76" }} tickLine={false} axisLine={{ stroke: "#d9d9d5" }} />
                <YAxis tick={{ fontSize: 11, fill: "#6b6f76" }} tickLine={false} axisLine={false} width={56}
                  tickFormatter={(v: number) => formatMinutes(v)} domain={["dataMin - 10", "dataMax + 10"]} />
                <Tooltip formatter={(v) => [formatMinutes(Number(v)), "Tiempo de viaje"]}
                  contentStyle={{ borderRadius: 8, border: "1px solid #ecece9", fontSize: 12 }} />
                <Line type="monotone" dataKey="minutes" stroke="#111113" strokeWidth={2} dot={{ r: 4, fill: "#111113" }} activeDot={{ r: 6 }} />
                <ReferenceDot x={best.label} y={best.minutes} r={7} fill="#1a7f4b" stroke="#fff" strokeWidth={2} />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </>
      ) : query.isFetching ? <div className="mt-4"><Spinner /></div> : null}
    </section>
  );
}
