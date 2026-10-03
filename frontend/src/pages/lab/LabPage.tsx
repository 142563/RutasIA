import { useQuery } from "@tanstack/react-query";
import { CheckIcon, PauseIcon, PlayIcon, RotateCcwIcon, StepForwardIcon } from "lucide-react";
import * as React from "react";
import { DataSourceNote } from "@/components/DataSourceNote";
import { NetworkMap } from "@/components/map/NetworkMap";
import { NodeSearch } from "@/components/NodeSearch";
import { Button } from "@/components/ui/button";
import { Field, Select } from "@/components/ui/field";
import { ErrorNote, PageHeader, Segmented, Spinner } from "@/components/ui/misc";
import { api } from "@/lib/api";
import { formatKm, formatMinutes } from "@/lib/format";
import { departureFor, isFinished, savingPct, totalSteps, visibleOrder } from "@/lib/lab";
import { useNetwork } from "@/lib/queries";
import { BANDS, type Band, type DayType } from "@/lib/traffic";
import type { GraphEdge, GraphNode, Meta, SearchPayload } from "@/lib/types";

type Algo = "dijkstra" | "astar";
type ExploreResult = SearchPayload & { order: string[] };
interface ExploreResponse extends Meta {
  explore: Record<Algo, ExploreResult>;
}

const ALGOS: { id: Algo; name: string; color: string; idea: string }[] = [
  { id: "dijkstra", name: "Dijkstra", color: "#2a78d6", idea: "Expande por tiempo acumulado g(n): crece en todas direcciones." },
  { id: "astar", name: "A*", color: "#eb6834", idea: "Expande por f(n) = g(n) + h(n), con h = distancia en línea recta / v_max." },
];
const SPEEDS = [
  { value: "1", label: "1×" },
  { value: "2", label: "2×" },
  { value: "4", label: "4×" },
];
const BASE_INTERVAL_MS = 280;

export function LabPage() {
  const network = useNetwork();
  const [origin, setOrigin] = React.useState<GraphNode | null>(null);
  const [destination, setDestination] = React.useState<GraphNode | null>(null);
  const [band, setBand] = React.useState<Band>("mid_morning");
  const [dayType, setDayType] = React.useState<DayType>("weekday");
  const [step, setStep] = React.useState(0);
  const [playing, setPlaying] = React.useState(false);
  const [speed, setSpeed] = React.useState("1");

  // Por defecto: Ciudad de Guatemala → Flores (el caso del flujo B, §8)
  React.useEffect(() => {
    if (!network.data || origin) return;
    setOrigin(network.data.nodes.find((n) => n.code === "ciudad-guatemala") ?? null);
    setDestination(network.data.nodes.find((n) => n.code === "flores") ?? null);
  }, [network.data, origin]);

  const departure = departureFor(band, dayType);
  const explore = useQuery({
    queryKey: ["explore", origin?.code, destination?.code, departure],
    queryFn: () => api<ExploreResponse>("/api/routing/explore/", {
      method: "POST", body: { origin: origin!.code, destination: destination!.code, departure },
    }),
    enabled: !!origin && !!destination && origin.code !== destination.code,
  });

  const result = explore.data?.explore;
  const steps = result ? totalSteps(result.dijkstra.order, result.astar.order) : 0;

  // Cada consulta nueva reinicia y reproduce la animación
  React.useEffect(() => {
    if (!result) return;
    setStep(0);
    setPlaying(true);
  }, [result]);

  React.useEffect(() => {
    if (!playing) return;
    if (step >= steps) {
      setPlaying(false);
      return;
    }
    const t = setTimeout(() => setStep((s) => s + 1), BASE_INTERVAL_MS / Number(speed));
    return () => clearTimeout(t);
  }, [playing, step, steps, speed]);

  const done = result ? step >= steps : false;
  const sameCost = result && result.dijkstra.cost !== null && result.astar.cost !== null
    && Math.abs(result.dijkstra.cost - result.astar.cost) <= 1e-9 * Math.max(1, result.dijkstra.cost);

  return (
    <div className="flex min-h-full flex-col">
      <PageHeader title="Laboratorio · Dijkstra vs A*" subtitle="La misma consulta con los dos algoritmos, sobre la red vial nacional." />

      <div className="flex flex-wrap items-end gap-3 border-b border-line px-6 py-4 lg:px-8">
        {network.data ? (
          <>
            <Field label="Origen" htmlFor="lab-origin" className="w-full sm:w-52">
              <NodeSearch key={`o-${origin?.code}`} id="lab-origin" nodes={network.data.nodes} placeholder={origin?.name ?? "Origen"} onSelect={setOrigin} />
            </Field>
            <Field label="Destino" htmlFor="lab-destination" className="w-full sm:w-52">
              <NodeSearch key={`d-${destination?.code}`} id="lab-destination" nodes={network.data.nodes} placeholder={destination?.name ?? "Destino"} onSelect={setDestination} />
            </Field>
          </>
        ) : null}
        <Field label="Franja" htmlFor="lab-band" className="w-full sm:w-52">
          <Select id="lab-band" value={band} onChange={(e) => setBand(e.target.value as Band)}>
            {BANDS.map((b) => <option key={b.id} value={b.id}>{b.label} · {b.hours}</option>)}
          </Select>
        </Field>
        <Segmented label="Tipo de día" value={dayType} onChange={setDayType}
          options={[{ value: "weekday", label: "Laboral" }, { value: "weekend", label: "Fin de semana" }]} />
      </div>

      <div className="flex flex-wrap items-center gap-2 border-b border-line px-6 py-3 lg:px-8">
        <Button size="sm" onClick={() => (done ? (setStep(0), setPlaying(true)) : setPlaying((p) => !p))} disabled={!result}>
          {playing ? <><PauseIcon /> Pausar</> : done ? <><RotateCcwIcon /> Repetir</> : <><PlayIcon /> Reproducir</>}
        </Button>
        <Button size="sm" variant="outline" onClick={() => { setPlaying(false); setStep((s) => Math.min(s + 1, steps)); }} disabled={!result || done}>
          <StepForwardIcon /> Paso
        </Button>
        <Button size="sm" variant="ghost" onClick={() => { setPlaying(false); setStep(0); }} disabled={!result || step === 0}>
          <RotateCcwIcon /> Reiniciar
        </Button>
        <Segmented label="Velocidad" value={speed} onChange={setSpeed} options={SPEEDS} />
        <span className="num ml-auto text-xs text-ink-2">Paso {Math.min(step, steps)} de {steps}</span>
      </div>

      {explore.isPending && explore.fetchStatus !== "idle" ? <div className="p-8"><Spinner label="Ejecutando los dos algoritmos…" /></div> : null}
      {explore.error ? <div className="p-6"><ErrorNote error={explore.error} /></div> : null}
      {origin && destination && origin.code === destination.code ? (
        <p className="px-8 py-6 text-sm text-ink-2">Elige un destino distinto del origen.</p>
      ) : null}

      {result && network.data ? (
        <>
          <div className="grid gap-px bg-line lg:grid-cols-2">
            {ALGOS.map((algo) => (
              <AlgoPanel
                key={algo.id}
                algo={algo}
                result={result[algo.id]}
                step={step}
                nodes={network.data!.nodes}
                edges={network.data!.edges}
                origin={origin!}
                destination={destination!}
                sameCost={!!sameCost}
              />
            ))}
          </div>
          <div className="flex flex-col gap-4 px-6 py-5 lg:px-8">
            {done ? (
              <p className="text-sm">
                A* expandió <b className="num">{result.astar.expanded}</b> nodos contra <b className="num">{result.dijkstra.expanded}</b> de
                Dijkstra (<b className="num text-ok">−{savingPct(result.dijkstra.expanded, result.astar.expanded)} %</b>)
                {sameCost ? <> y encontró el <b>mismo costo</b>: {formatMinutes(result.astar.minutes)} con el tráfico de {explore.data?.band_label?.toLowerCase()}.</> : "."}
              </p>
            ) : (
              <p className="text-sm text-ink-2">Los dos algoritmos avanzan un nodo por paso. Observa hacia dónde se expande cada uno.</p>
            )}
            <details className="text-[13px] text-ink-3">
              <summary className="cursor-pointer text-ink">¿Por qué A* da el mismo resultado explorando menos?</summary>
              <p className="mt-2 max-w-3xl">
                La heurística es h(n) = distancia en línea recta al destino / v_max, donde v_max es la mayor velocidad en línea recta
                que se observa en cualquier arista con el tráfico de esta franja. Por construcción h nunca sobreestima el tiempo que falta
                (es admisible) y cumple h(u) ≤ costo(u,v) + h(v) (es consistente). Por eso A* cierra cada nodo una sola vez con su costo
                óptimo y devuelve exactamente el mismo costo que Dijkstra, pero guiado hacia el destino.
              </p>
              <p className="mt-2 max-w-3xl">
                Los milisegundos son de una sola corrida y, en un grafo de ~100 nodos, son diminutos y ruidosos: la métrica principal
                es la cantidad de nodos expandidos. La ventaja en tiempo aparece en grafos grandes (experimento E7).
              </p>
            </details>
            <DataSourceNote source={explore.data?.data_source} />
          </div>
        </>
      ) : null}
    </div>
  );
}

function AlgoPanel({ algo, result, step, nodes, edges, origin, destination, sameCost }: {
  algo: (typeof ALGOS)[number];
  result: ExploreResult;
  step: number;
  nodes: GraphNode[];
  edges: GraphEdge[];
  origin: GraphNode;
  destination: GraphNode;
  sameCost: boolean;
}) {
  const visible = visibleOrder(result.order, step);
  const finished = isFinished(result.order, step);
  return (
    <section className="flex flex-col bg-surface" aria-label={algo.name}>
      <div className="flex flex-wrap items-start justify-between gap-3 px-5 pt-4">
        <div>
          <h2 className="flex items-center gap-2 text-base font-semibold">
            <span className="size-3 rounded-full" style={{ background: algo.color }} aria-hidden />
            {algo.name}
          </h2>
          <p className="mt-0.5 max-w-xs text-xs text-ink-2">{algo.idea}</p>
        </div>
        {finished && sameCost ? (
          <span className="flex items-center gap-1 text-xs font-medium text-ok"><CheckIcon className="size-3.5" /> Costo idéntico</span>
        ) : null}
      </div>
      <dl className="grid grid-cols-3 gap-3 px-5 py-3">
        <div>
          <dt className="text-xs text-ink-2">Nodos expandidos</dt>
          <dd className="num text-2xl font-medium">{visible.length}</dd>
        </div>
        <div>
          <dt className="text-xs text-ink-2">Tiempo de cómputo</dt>
          <dd className="num text-2xl font-medium">{finished ? `${result.elapsed_ms.toFixed(2)}` : "—"}<span className="text-sm text-ink-2"> ms</span></dd>
        </div>
        <div>
          <dt className="text-xs text-ink-2">Costo de la ruta</dt>
          <dd className="num text-2xl font-medium">{finished ? formatMinutes(result.minutes) : "—"}</dd>
        </div>
      </dl>
      <div className="px-2 pb-2">
        <NetworkMap
          nodes={nodes}
          edges={edges}
          labels="none"
          nodeMarks={visible.map((code) => ({ code, color: algo.color, r: 5.5, opacity: 0.35 }))}
          paths={finished ? [{ codes: result.nodes.map((n) => n.code), color: algo.color, width: 4.5, followRoads: true }] : []}
          markers={[
            { id: "o", kind: "stop", lat: origin.lat, lng: origin.lng, label: "A" },
            { id: "d", kind: "stop", lat: destination.lat, lng: destination.lng, label: "B" },
          ]}
          ariaLabel={`Nodos explorados por ${algo.name}`}
        />
      </div>
      {finished ? (
        <p className="num border-t border-line px-5 py-2.5 text-xs text-ink-2">
          {formatKm(result.km)} · {result.roads.join(" → ") || "—"}
        </p>
      ) : null}
    </section>
  );
}
