import { TriangleAlertIcon } from "lucide-react";
import type { ReactElement } from "react";
import { Bar, BarChart, CartesianGrid, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { ErrorNote, Metric, PageHeader, Spinner } from "@/components/ui/misc";
import { useReports, type ExperimentResult } from "@/lib/dispatch";
import { formatMinutes } from "@/lib/format";
import { formatWhen } from "@/pages/routes/shared";

const AXIS = { fontSize: 11, fill: "#6b6f76" };
const DIJKSTRA = "#2a78d6";
const ASTAR = "#eb6834";
const NEUTRAL = "#56595f";

const num = (v: unknown, digits = 1) => (typeof v === "number" ? v.toLocaleString("es-GT", { maximumFractionDigits: digits }) : "—");

function Chart({ title, height = 220, empty, children }: {
  title: string; height?: number; empty?: string; children: ReactElement;
}) {
  return (
    <figure className="min-w-0">
      <figcaption className="mb-2 text-[13px] font-medium">{title}</figcaption>
      {empty ? <p className="text-[13px] text-ink-2">{empty}</p> : (
        <div style={{ height }}>
          <ResponsiveContainer width="100%" height="100%">{children}</ResponsiveContainer>
        </div>
      )}
    </figure>
  );
}

/** Aviso de fuente: los experimentos con datos estimados o sintéticos NO son resultados de tesis. */
function ExperimentSource({ result }: { result: ExperimentResult }) {
  const synthetic = result.key === "e7";
  return (
    <div>
      <p className="num text-xs text-ink-2">Fuente: {result.data_sources.join(" · ") || "no indicada"}</p>
      {!result.is_real_data ? (
        <p className="mt-2 flex items-start gap-2 rounded-lg border border-warn/25 bg-warn/5 px-3 py-2 text-[13px] text-warn">
          <TriangleAlertIcon className="mt-0.5 size-4 shrink-0" aria-hidden />
          <span>
            {synthetic
              ? "Grafos sintéticos por diseño (prueban la escalabilidad, no representan a Guatemala). "
              : "Datos estimados o sintéticos. "}
            <b>No son resultados de tesis.</b>
          </span>
        </p>
      ) : null}
    </div>
  );
}

function ExperimentBody({ result }: { result: ExperimentResult }) {
  const s = result.summary as Record<string, unknown>;
  const cell = "border-b border-line py-2 pr-4 text-[13px]";
  const head = "border-b border-line py-2 pr-4 text-left text-xs font-normal text-ink-2";
  switch (result.key) {
    case "e1":
      return (
        <p className="text-sm">
          <span className="num font-medium">{num(s.equal, 0)}</span> de <span className="num">{num(s.queries, 0)}</span> consultas con costo(A*) = costo(Dijkstra)
          {" "}(<span className="num">{num(s.pct_equal, 2)} %</span>).
        </p>
      );
    case "e2":
      return (
        <div className="grid gap-6 sm:grid-cols-2">
          <div className="grid grid-cols-2 gap-4">
            <Metric label="Nodos expandidos, Dijkstra" value={num(s.dijkstra_expanded)} />
            <Metric label="Nodos expandidos, A*" value={num(s.astar_expanded)} hint={`${num(s.reduction_pct)} % menos`} />
            <Metric label="Milisegundos, Dijkstra" value={num(s.dijkstra_ms, 3)} />
            <Metric label="Milisegundos, A*" value={num(s.astar_ms, 3)} />
          </div>
          <Chart title="Nodos expandidos por consulta (promedio)" height={180}>
            <BarChart data={[{ name: "Dijkstra", nodos: s.dijkstra_expanded }, { name: "A*", nodos: s.astar_expanded }]}>
              <CartesianGrid stroke="#ecece9" vertical={false} />
              <XAxis dataKey="name" tick={AXIS} axisLine={false} tickLine={false} />
              <YAxis tick={AXIS} axisLine={false} tickLine={false} width={40} />
              <Tooltip />
              <Bar dataKey="nodos" name="Nodos" fill={DIJKSTRA} radius={[3, 3, 0, 0]} />
            </BarChart>
          </Chart>
        </div>
      );
    case "e3":
      return (
        <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
          <Metric label="Casos" value={num(s.cases, 0)} />
          <Metric label="La más rápida ≠ la más corta" value={num(s.route_changes, 0)} hint="casos" />
          <Metric label="Ahorro promedio" value={formatMinutes(s.mean_minutes_saved as number)} />
          <Metric label="Ahorro máximo" value={formatMinutes(s.max_minutes_saved as number)} />
        </div>
      );
    case "e5": {
      const data = (s.by_stops as { stops: number; two_opt_vs_capture_pct: number; two_opt_vs_nn_pct: number }[]) ?? [];
      return (
        <Chart title="Mejora de 2-opt según el número de paradas (%)" height={200}>
          <BarChart data={data.map((d) => ({ name: `${d.stops} paradas`, capture: d.two_opt_vs_capture_pct, nn: d.two_opt_vs_nn_pct }))}>
            <CartesianGrid stroke="#ecece9" vertical={false} />
            <XAxis dataKey="name" tick={AXIS} axisLine={false} tickLine={false} />
            <YAxis tick={AXIS} axisLine={false} tickLine={false} width={40} />
            <Tooltip />
            <Legend wrapperStyle={{ fontSize: 12 }} />
            <Bar dataKey="capture" name="Frente al orden de captura" fill={NEUTRAL} radius={[3, 3, 0, 0]} />
            <Bar dataKey="nn" name="Frente al vecino más cercano" fill={ASTAR} radius={[3, 3, 0, 0]} />
          </BarChart>
        </Chart>
      );
    }
    default: {
      const rows = (s.by_size as { nodes: number; graph: string; dijkstra_expanded: number; astar_expanded: number; dijkstra_ms: number; astar_ms: number }[]) ?? [];
      return (
        <div className="overflow-x-auto">
          <table className="w-full min-w-[520px]">
            <thead>
              <tr>
                <th className={head}>Grafo</th>
                <th className={`${head} text-right`}>Nodos</th>
                <th className={`${head} text-right`}>Expandidos Dijkstra</th>
                <th className={`${head} text-right`}>Expandidos A*</th>
                <th className={`${head} text-right`}>ms Dijkstra</th>
                <th className={`${head} text-right`}>ms A*</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => (
                <tr key={`${r.graph}-${r.nodes}`}>
                  <td className={cell}>{r.graph}</td>
                  <td className={`${cell} num text-right`}>{num(r.nodes, 0)}</td>
                  <td className={`${cell} num text-right`}>{num(r.dijkstra_expanded)}</td>
                  <td className={`${cell} num text-right`}>{num(r.astar_expanded)}</td>
                  <td className={`${cell} num text-right`}>{num(r.dijkstra_ms, 3)}</td>
                  <td className={`${cell} num text-right`}>{num(r.astar_ms, 3)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      );
    }
  }
}

export function ReportsPage() {
  const query = useReports();
  const data = query.data;

  return (
    <div>
      <PageHeader title="Reportes" subtitle="Minutos ahorrados, puntualidad y resultados de los experimentos" />
      {query.isPending ? <div className="p-8"><Spinner /></div> : null}
      {query.error ? <div className="p-6 lg:px-8"><ErrorNote error={query.error} /></div> : null}
      {data ? (
        <div className="flex flex-col gap-10 px-6 py-6 lg:px-8">
          <section aria-label="Operación" className="flex flex-col gap-6">
            <div className="grid grid-cols-2 gap-6 border-b border-line pb-6 sm:grid-cols-4">
              <Metric label="Minutos ahorrados" value={formatMinutes(data.minutes_saved.total)}
                hint={`En ${data.minutes_saved.routes} rutas, frente a la más corta`} />
              <Metric label="Puntualidad" value={data.punctuality.pct != null ? `${data.punctuality.pct} %` : "—"}
                hint={data.punctuality.delivered > 0
                  ? `${data.punctuality.on_time} de ${data.punctuality.delivered} entregas, tolerancia ${data.punctuality.tolerance_min} min`
                  : "Aún no hay entregas"} />
              <Metric label="Entregas fallidas" value={data.failed_by_reason.reduce((sum, r) => sum + r.count, 0)} />
              <Metric label="Rutas con ahorro medido" value={data.minutes_saved.routes} />
            </div>
            <div className="grid gap-8 lg:grid-cols-2">
              <Chart title="Minutos ahorrados por ruta" empty={data.minutes_saved.by_route.length === 0 ? "Aún no hay rutas planificadas." : undefined}>
                <BarChart data={data.minutes_saved.by_route}>
                    <CartesianGrid stroke="#ecece9" vertical={false} />
                    <XAxis dataKey="code" tick={false} axisLine={false} tickLine={false} />
                    <YAxis tick={AXIS} axisLine={false} tickLine={false} width={40} />
                    <Tooltip />
                    <Bar dataKey="minutes_saved" name="Minutos ahorrados" fill={NEUTRAL} radius={[3, 3, 0, 0]} />
                </BarChart>
              </Chart>
              <Chart title="Entregas fallidas por motivo" empty={data.failed_by_reason.length === 0 ? "No hay entregas fallidas." : undefined}>
                <BarChart data={data.failed_by_reason} layout="vertical" margin={{ left: 8 }}>
                    <CartesianGrid stroke="#ecece9" horizontal={false} />
                    <XAxis type="number" allowDecimals={false} tick={AXIS} axisLine={false} tickLine={false} />
                    <YAxis type="category" dataKey="reason" tick={AXIS} axisLine={false} tickLine={false} width={120} />
                    <Tooltip />
                    <Bar dataKey="count" name="Entregas" fill="#b42318" radius={[0, 3, 3, 0]} />
                </BarChart>
              </Chart>
            </div>
          </section>

          <section aria-label="Experimentos" className="flex flex-col gap-2">
            <h2 className="text-sm font-semibold">Experimentos</h2>
            <p className="text-[13px] text-ink-2">
              Resúmenes de los CSV que deja <span className="num">python manage.py run_experiments</span>.
            </p>
            {data.experiments.length === 0 ? (
              <p className="border-t border-line py-6 text-[13px] text-ink-2">
                Todavía no hay resultados. Corre <span className="num">run_experiments</span> para generarlos.
              </p>
            ) : (
              data.experiments.map((exp) => (
                <article key={exp.key} className="flex flex-col gap-4 border-t border-line py-6">
                  <header className="flex flex-wrap items-baseline justify-between gap-2">
                    <h3 className="text-sm font-medium">{exp.title}</h3>
                    <span className="num text-xs text-ink-2">{exp.rows} filas · {formatWhen(exp.updated_at)}</span>
                  </header>
                  <ExperimentBody result={exp} />
                  <ExperimentSource result={exp} />
                </article>
              ))
            )}
          </section>
        </div>
      ) : null}
    </div>
  );
}
