import { Link, useParams } from "react-router";
import { ErrorNote, Spinner } from "@/components/ui/misc";
import { useRouteDetail } from "@/lib/dispatch";
import { formatClock, formatKm, formatMinutes } from "@/lib/format";
import { useOrders } from "@/lib/orders";
import { routeSheetStops } from "@/lib/routeSheet";
import "./route-print.css";

export function RoutePrintPage() {
  const { routeId } = useParams();
  const detail = useRouteDetail(routeId);
  const orders = useOrders({ status: "all" });
  const route = detail.data?.route;
  const rows = routeSheetStops(route?.stops ?? [], orders.data?.orders ?? []);
  const loading = detail.isPending || orders.isPending || detail.isFetching || orders.isFetching;
  const error = detail.error ?? orders.error;
  const missing = rows.some((row) => row.reference === null);
  const ready = !!route && !loading && !error && !missing;

  return (
    <main className="route-print min-h-screen bg-bg px-4 py-6 text-ink sm:px-8">
      <div className="route-print-controls mx-auto mb-6 flex max-w-5xl flex-wrap items-center justify-between gap-3">
        <Link to={`/rutas/${routeId}`} className="rounded-md px-3 py-3 text-sm hover:bg-hover">Volver a la ruta</Link>
        <button type="button" disabled={!ready} onClick={() => window.print()}
          className="min-h-11 rounded-lg bg-ink px-4 py-3 text-sm font-medium text-on-ink disabled:cursor-not-allowed disabled:opacity-50">
          Imprimir hoja de ruta
        </button>
      </div>
      {loading ? <div role="status" className="route-print-controls mx-auto max-w-5xl"><Spinner /> Cargando hoja de ruta…</div> : null}
      {error ? <div className="route-print-controls mx-auto max-w-5xl"><ErrorNote error={error} /></div> : null}
      {!loading && !error && missing ? <p role="alert" className="route-print-controls mx-auto max-w-5xl text-err">No se encontraron todos los pedidos de esta ruta. Vuelve a cargar la página antes de imprimir.</p> : null}
      {ready ? (
        <article className="route-sheet mx-auto max-w-5xl rounded-lg border border-line bg-surface p-4 shadow-card sm:p-8">
          <header className="mb-5 border-b border-line pb-4">
            <p className="mb-1 text-sm text-ink-2">enruta · Hoja de ruta</p>
            <h1 className="num text-2xl font-semibold">{route.code}</h1>
            <dl className="mt-4 grid grid-cols-2 gap-x-6 gap-y-3 text-sm sm:grid-cols-3">
              {[
                ["Fecha", new Date(route.departure_at).toLocaleDateString("es-GT", { timeZone: "America/Guatemala", year: "numeric", month: "long", day: "numeric" })],
                ["Bodega", route.depot], ["Conductor", route.driver ?? "Sin asignar"],
                ["Vehículo", route.vehicle ?? "Sin asignar"], ["Salida estimada", formatClock(route.departure_at)],
                ["Llegada estimada", formatClock(route.finish_at)], ["Distancia total", formatKm(route.total_km)],
                ["Tiempo de manejo total", formatMinutes(route.driving_minutes)],
              ].map(([label, value]) => <div key={label}><dt className="text-xs text-ink-2">{label}</dt><dd className="mt-1 break-words font-medium">{value}</dd></div>)}
            </dl>
            <p className="mt-3 text-xs text-ink-2">Horas de Guatemala. Los horarios son estimados; el tiempo de manejo no incluye el servicio en las paradas.</p>
          </header>
          <div className="route-sheet-table-wrap overflow-x-auto">
            <table className="route-sheet-table w-full min-w-[720px] table-fixed border-collapse text-left text-xs">
              <caption className="mb-3 text-left text-sm font-semibold">Paradas en orden de visita</caption>
              <colgroup><col style={{ width: "5%" }} /><col style={{ width: "17%" }} /><col style={{ width: "26%" }} /><col style={{ width: "18%" }} /><col style={{ width: "12%" }} /><col style={{ width: "9%" }} /><col style={{ width: "13%" }} /></colgroup>
              <thead><tr>{["N.º", "Destinatario", "Dirección", "Referencia", "Teléfono", "Hora estimada", "Firma"].map((label) => <th key={label} scope="col" className="border border-line px-2 py-2 font-semibold">{label}</th>)}</tr></thead>
              <tbody>{rows.map((stop) => <tr key={stop.id}>
                <td className="num">{stop.sequence}</td><td>{stop.recipient}<span className="num mt-1 block text-ink-2">{stop.order_code}</span></td>
                <td>{stop.address}</td><td>{stop.reference || "—"}</td><td className="num">{stop.phone || "—"}</td><td className="num">{formatClock(stop.eta)}</td>
                <td aria-label={`Firma de ${stop.recipient}`}><div className="min-h-12" /></td>
              </tr>)}</tbody>
            </table>
          </div>
          {rows.length === 0 ? <p className="mt-3 text-sm">Esta ruta no tiene paradas.</p> : null}
        </article>
      ) : <p className="route-print-unavailable hidden">La hoja de ruta no está lista. Espera que cargue o resuelve el error antes de imprimir.</p>}
    </main>
  );
}
