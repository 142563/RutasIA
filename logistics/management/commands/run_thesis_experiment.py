import csv
import json
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand

from django.db import DatabaseError

from logistics.application.routing import optimizer_params
from logistics.routing.genetic import GeneticParams
from logistics.models import Node
from logistics.routing import thesis_experiment as tx
from logistics.routing.graph import invalidate_graph, load_graph


class Command(BaseCommand):
    help = ("Experimento de la tesis: ruta convencional (proximidad sucesiva) vs. optimizada (genético), "
            "3 escenarios × 10 repeticiones, más la línea base OR-Tools y la estadística (requirements-dev.txt).")

    def add_arguments(self, parser):
        parser.add_argument("--out", default=str(Path(settings.BASE_DIR) / "docs" / "Capitulo V" / "resultados"),
                            help="Carpeta de salida.")
        parser.add_argument("--seed", type=int, default=2026)
        parser.add_argument("--repetitions", type=int, default=tx.REPETITIONS)
        parser.add_argument("--ortools-seconds", type=int, default=10,
                            help="Límite de tiempo de OR-Tools por instancia.")
        parser.add_argument("--no-ortools", action="store_true", help="Omite la línea base OR-Tools.")

    def handle(self, *args, **options):
        invalidate_graph()
        graph = load_graph()
        departments = dict(Node.objects.values_list("code", "department"))
        sources = ";".join(f"{k}={v}" for k, v in sorted(graph.sources.items()))
        self.stdout.write(f"Grafo: {graph.node_count} nodos, {graph.edge_count} aristas · fuente {sources}")
        if any(v != "google" and not v.startswith("google") for v in graph.sources.values()):
            self.stdout.write(self.style.WARNING(
                "Datos NO reales de Google: estos resultados no son aptos para la tesis."))

        baseline = None
        if not options["no_ortools"]:
            from logistics.routing.baseline_ortools import solve

            def baseline(matrix):
                result = solve(matrix, return_to_depot=True, time_limit_s=options["ortools_seconds"])
                return result.cost, result.ms

        try:
            params = optimizer_params()
        except DatabaseError:  # BD sin la migración del optimizador: valores por defecto
            params = GeneticParams()
        rows, baseline_rows = tx.run(graph, departments, seed=options["seed"], repetitions=options["repetitions"],
                                     params=params, baseline=baseline, progress=self.stdout.write)
        response_50 = tx.response_time_50(graph, options["seed"], params)
        report = tx.statistics_report(rows, baseline_rows, response_50)
        report["fuente_datos"] = sources
        report["parametros_genetico"] = params.__dict__
        report["semilla"] = options["seed"]

        out = Path(options["out"])
        out.mkdir(parents=True, exist_ok=True)
        self._csv(rows, out / "matriz_comparativa.csv")
        if baseline_rows:
            self._csv(baseline_rows, out / "genetico_vs_ortools.csv")
        (out / "estadistica.json").write_text(json.dumps(report, ensure_ascii=False, indent=2, default=str),
                                              encoding="utf-8")

        total = report["total"]
        self.stdout.write(self.style.SUCCESS(f"Resultados en {out}"))
        self.stdout.write(f"Distancia: {total['distancia_km']['reduccion_media_pct']} % "
                          f"({total['distancia_km']['prueba']}, p = {total['distancia_km']['p_valor']})")
        self.stdout.write(f"Tiempo: {total['tiempo_min']['reduccion_media_pct']} % "
                          f"({total['tiempo_min']['prueba']}, p = {total['tiempo_min']['p_valor']})")
        self.stdout.write(f"Ruta alternativa: {report['ruta_alternativa']['exito_pct']} % · respuesta máx. "
                          f"{report['tiempo_respuesta']['max_s']} s · H0 rechazada: {report['h0_distancia']['rechazada']}")

    @staticmethod
    def _csv(rows, path):
        # utf-8-sig: Excel abre bien los acentos
        with open(path, "w", newline="", encoding="utf-8-sig") as fh:
            writer = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
            writer.writeheader()
            writer.writerows(rows)
