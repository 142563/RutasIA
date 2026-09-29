from django.core.management.base import BaseCommand, CommandError

from logistics.models import Node
from logistics.routing.build import build_estimated, build_from_google
from logistics.routing.google import RoutesApiError, RoutesClient
from logistics.routing.seed_data import ROAD_SEGMENTS


class Command(BaseCommand):
    help = (
        "Construye las aristas dirigidas del grafo nacional a partir de los tramos candidatos. "
        "Con Google Routes API (por defecto) o estimadas sin conexión (--estimate)."
    )

    def add_arguments(self, parser):
        parser.add_argument("--estimate", action="store_true",
                            help="Sin conexión: km y minutos estimados (NO aptos para la tesis).")
        parser.add_argument("--refresh", action="store_true",
                            help="Vuelve a pedir a Google aunque haya muestras recientes.")

    def handle(self, *args, **options):
        if not Node.objects.exists():
            raise CommandError("No hay nodos. Corre primero: python manage.py seed_graph_nodes")

        if options["estimate"]:
            report = build_estimated()
            self.stdout.write(self.style.WARNING(
                "Modo sin conexión: aristas ESTIMADAS (source=estimate). No usar en el documento de tesis."
            ))
        else:
            try:
                client = RoutesClient()
            except RoutesApiError as exc:
                raise CommandError(str(exc)) from exc
            pairs = 2 * len(ROAD_SEGMENTS)
            self.stdout.write(f"Verificando {pairs} aristas dirigidas con Google Routes API…")
            report = build_from_google(client, refresh=options["refresh"])
            self.stdout.write(f"Solicitudes a Google: {report.requests} ({report.elements} elementos).")

        self.stdout.write(self.style.SUCCESS(
            f"Aristas: {report.edges_created} nuevas, {report.edges_updated} actualizadas, "
            f"{report.edges_skipped} omitidas."
        ))
        for a, b, status in report.not_found:
            self.stdout.write(self.style.ERROR(f"  Sin ruta {a} -> {b}: {status}"))
        for a, b, ratio in report.detours:
            self.stdout.write(self.style.WARNING(f"  Rodeo {a} -> {b}: {ratio:.1f}× la línea recta (revisar)"))
        for a, b in report.redundant:
            self.stdout.write(self.style.WARNING(f"  Redundante {a} -> {b}: pasa por otro nodo; desactivada"))
