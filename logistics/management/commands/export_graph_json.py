import json
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand

from logistics.models import Node
from logistics.routing.graph import invalidate_graph, load_graph


class Command(BaseCommand):
    help = ("Exporta el grafo en memoria (nodos, aristas, t0, km, clase de vía y multiplicadores por franja) "
            "a JSON, para los cuadernos de experiments/colab/ (corren en Colab sin la BD).")

    def add_arguments(self, parser):
        parser.add_argument("--out", default=str(Path(settings.BASE_DIR) / "experiments" / "colab" / "grafo.json"))

    def handle(self, *args, **options):
        invalidate_graph()
        g = load_graph()
        departments = dict(Node.objects.values_list("code", "department"))
        data = {
            "fuente_datos": g.sources,
            "nodos": [{"code": c, "name": n, "lat": la, "lon": lo, "department": departments.get(c, "")}
                      for c, n, la, lo in zip(g.codes, g.names, g.lat, g.lon)],
            "aristas": [{"from": g.codes[u], "to": g.codes[v], "t0_min": round(t, 4), "km": round(k, 4),
                         "road_class": rc, "road": road}
                        for u, v, t, k, rc, road in zip(g.edge_from, g.edge_to, g.t0, g.km, g.road_classes, g.roads)],
            # multiplicadores[franja|tipo_de_día][i] corresponde a aristas[i]
            "multiplicadores": {f"{band}|{day}": [round(m, 4) for m in values]
                                for (band, day), values in sorted(g.multipliers.items())},
        }
        out = Path(options["out"])
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        self.stdout.write(self.style.SUCCESS(
            f"{out}: {g.node_count} nodos, {g.edge_count} aristas, {len(g.multipliers)} perfiles ({g.sources})"))
