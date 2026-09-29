import csv
import statistics
import time
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from logistics.routing import charts, experiments
from logistics.routing.google import RoutesApiError, RoutesClient
from logistics.routing.graph import invalidate_graph, load_graph

EXPERIMENTS = ("e1", "e2", "e3", "e4", "e5", "e6", "e7")


class Command(BaseCommand):
    help = "Corre los experimentos E1 a E7 y genera CSV (y gráficas si hay matplotlib)."

    def add_arguments(self, parser):
        parser.add_argument("--only", nargs="+", choices=EXPERIMENTS, help="Correr solo algunos experimentos.")
        parser.add_argument("--out", default=str(Path(settings.BASE_DIR) / "experiments" / "output"),
                            help="Carpeta de salida (por defecto experiments/output/).")
        parser.add_argument("--max-nodes", type=int, default=100_000, help="Tamaño máximo de grafo en E7.")
        parser.add_argument("--reps", type=int, default=5, help="Repeticiones por búsqueda para medir ms.")
        parser.add_argument("--quick", action="store_true", help="Versión corta (para pruebas).")
        parser.add_argument("--no-charts", action="store_true", help="Solo CSV.")
        parser.add_argument("--with-google", action="store_true",
                            help="E4: consulta Google Routes API (gasta cuota; pide confirmación). "
                                 "Sin esta bandera E4 solo usa la caché RouteSample.")
        parser.add_argument("--yes", action="store_true", help="E4: no pedir confirmación antes de consultar a Google.")
        parser.add_argument("--e4-trips", type=int, default=50, help="E4: número de viajes muestreados (semilla fija).")
        parser.add_argument("--refresh", action="store_true", help="E4: vuelve a pedir a Google aunque haya caché.")

    def run_e4(self, graph, options, out, make_charts):
        quick = options["quick"]
        trips = experiments.e4_trips(graph, count=8 if quick else options["e4_trips"])
        client = None
        if options["with_google"]:
            try:
                client = RoutesClient()
            except RoutesApiError as exc:
                self.stdout.write(self.style.WARNING(f"E4 omitido: {exc}"))
                return
            needed = len(trips) if options["refresh"] else experiments.e4_pending(trips)
            self.stdout.write(f"E4: se consultarán hasta {needed} elementos de Routes API con tráfico "
                              f"({len(trips)} viajes; los recientes salen de la caché).")
            if needed and not options["yes"] and input("¿Continuar? [s/N] ").strip().lower() not in ("s", "si", "sí", "y", "yes"):
                self.stdout.write(self.style.WARNING("E4 omitido: consulta a Google cancelada."))
                return
        rows = experiments.e4_precision(graph, trips, client=client, refresh=options["refresh"])
        if not rows:
            self.stdout.write(self.style.WARNING(
                "E4 omitido: no hay respuestas de Google en la caché. Requiere GOOGLE_ROUTES_API_KEY y la "
                "bandera --with-google (consulta la API y pide confirmación)."))
            return
        self.write_csv(rows, out / "e4_precision.csv")
        summary = experiments.e4_summary(rows)
        self.write_csv(summary, out / "e4_resumen.csv")
        self.stdout.write(f"E4: MAPE global {summary[0]['mape_pct']:.1f} % en {len(rows)} viajes "
                          f"(objetivo < 20 %; sesgo {summary[0]['bias_pct']:+.1f} %)")
        if make_charts:
            self.stdout.write(f"  {charts.e4_chart(rows, out)}")

    def write_csv(self, rows, path: Path):
        if not rows:
            self.stdout.write(self.style.WARNING(f"  {path.name}: sin filas"))
            return
        with path.open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)
        self.stdout.write(f"  {path}  ({len(rows)} filas)")

    def handle(self, *args, **options):
        selected = options["only"] or EXPERIMENTS
        out = Path(options["out"])
        out.mkdir(parents=True, exist_ok=True)
        quick, reps = options["quick"], options["reps"]
        make_charts = not options["no_charts"] and charts.available()
        if not options["no_charts"] and not make_charts:
            self.stdout.write(self.style.WARNING(
                "matplotlib no está instalado: solo se generan CSV (pip install -r requirements-dev.txt)."))

        graph = None
        if set(selected) - {"e7"}:
            invalidate_graph()
            graph = load_graph()
            if graph.edge_count == 0:
                raise CommandError("El grafo está vacío: corre seed_graph_nodes y build_graph.")
            source = experiments.data_source(graph)
            self.stdout.write(f"Grafo: {graph.node_count} nodos, {graph.edge_count} aristas · {source}")
            if "estimate" in source or "synthetic" in source or "none" in source:
                self.stdout.write(self.style.WARNING(
                    "ATENCIÓN: datos estimados/sintéticos. Sirven para probar, NO para el documento de tesis."))

        started = time.perf_counter()
        if "e1" in selected:
            rows = experiments.e1_correctness(graph, quick=quick)
            self.write_csv(rows, out / "e1_correctitud.csv")
            pairs, equal = sum(r["pairs"] for r in rows), sum(r["equal"] for r in rows)
            style = self.style.SUCCESS if pairs == equal else self.style.ERROR
            self.stdout.write(style(f"E1: {equal}/{pairs} consultas con costo(A*) = costo(Dijkstra) "
                                    f"({100 * equal / pairs:.2f} %)"))
        if "e2" in selected:
            rows = experiments.e2_efficiency(graph, reps=1 if quick else reps, quick=quick)
            self.write_csv(rows, out / "e2_eficiencia.csv")
            d = statistics.mean(r["dijkstra_expanded"] for r in rows)
            a = statistics.mean(r["astar_expanded"] for r in rows)
            self.stdout.write(f"E2: nodos expandidos promedio Dijkstra {d:.1f} · A* {a:.1f} "
                              f"({100 * (1 - a / d):.1f} % menos)")
            if make_charts:
                self.stdout.write(f"  {charts.e2_chart(rows, out)}")
        if "e3" in selected:
            rows = experiments.e3_traffic_impact(graph, quick=quick)
            self.write_csv(rows, out / "e3_impacto_trafico.csv")
            changed = sum(r["route_changes"] for r in rows)
            self.stdout.write(f"E3: la ruta más rápida difiere de la más corta en {changed}/{len(rows)} casos; "
                              f"ahorro máximo {max(r['minutes_saved'] for r in rows):.1f} min")
            if make_charts:
                self.stdout.write(f"  {charts.e3_chart(rows, out)}")
        if "e4" in selected:
            self.run_e4(graph, options, out, make_charts)
        if "e6" in selected:
            rows = experiments.e6_departure_time(graph, quick=quick)
            self.write_csv(rows, out / "e6_hora_de_salida.csv")
            if rows:
                best = min(rows, key=lambda r: r["minutes"])
                worst = max(rows, key=lambda r: r["minutes"])
                self.stdout.write(f"E6: {len({r['pair'] for r in rows})} viajes · tiempo mínimo {best['minutes']:.0f} min "
                                  f"({best['pair']}, {best['band']}/{best['day_type']}) · máximo "
                                  f"{worst['minutes']:.0f} min ({worst['pair']}, {worst['band']}/{worst['day_type']})")
                if make_charts:
                    self.stdout.write(f"  {charts.e6_chart(rows, out)}")
        if "e5" in selected:
            rows = experiments.e5_multistop(graph, instances=3 if quick else 30,
                                            sizes=(5, 10) if quick else (5, 10, 15, 20))
            self.write_csv(rows, out / "e5_varias_paradas.csv")
            self.stdout.write(f"E5: 2-opt mejora el orden de captura en "
                              f"{statistics.mean(r['two_opt_vs_capture_pct'] for r in rows):.1f} % en promedio")
            if make_charts:
                self.stdout.write(f"  {charts.e5_chart(rows, out)}")
        if "e7" in selected:
            rows = experiments.e7_scalability(max_nodes=options["max_nodes"], queries=3 if quick else 20,
                                              reps=1 if quick else 3)
            self.write_csv(rows, out / "e7_escalabilidad.csv")
            for n in sorted({r["nodes"] for r in rows}):
                sub = [r for r in rows if r["nodes"] == n]
                self.stdout.write(
                    f"E7: {n} nodos · expandidos Dijkstra {statistics.mean(r['dijkstra_expanded'] for r in sub):.0f}"
                    f" · A* {statistics.mean(r['astar_expanded'] for r in sub):.0f}"
                    f" · mismo costo {all(r['same_cost'] for r in sub)}")
            if make_charts:
                self.stdout.write(f"  {charts.e7_chart(rows, out)}")

        self.stdout.write(self.style.SUCCESS(
            f"Listo en {time.perf_counter() - started:.1f} s · {experiments.run_date()} · {out}"))
