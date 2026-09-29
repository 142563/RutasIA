from collections import Counter

from django.core.management.base import BaseCommand
from django.db import transaction

from logistics.models import Node
from logistics.routing.seed_data import NODES, ROAD_SEGMENTS


class Command(BaseCommand):
    help = (
        "Carga los nodos semilla del grafo nacional. Se puede repetir: actualiza por código. "
        "No crea aristas; eso lo hace build_graph con Google Routes API."
    )

    @transaction.atomic
    def handle(self, *args, **options):
        created = 0
        for seed in NODES:
            _, was_created = Node.objects.update_or_create(
                code=seed.code,
                defaults={
                    "name": seed.name,
                    "kind": seed.kind,
                    "department": seed.department,
                    "latitude": seed.latitude,
                    "longitude": seed.longitude,
                    "is_active": True,
                },
            )
            created += was_created

        by_kind = Counter(seed.kind for seed in NODES)
        summary = ", ".join(f"{count} {kind}" for kind, count in sorted(by_kind.items()))
        self.stdout.write(self.style.SUCCESS(
            f"Nodos: {len(NODES)} ({summary}); {created} nuevos, {len(NODES) - created} actualizados."
        ))
        self.stdout.write(
            f"Tramos candidatos en seed_data: {len(ROAD_SEGMENTS)} "
            f"({sum(s.needs_check for s in ROAD_SEGMENTS)} por verificar)."
        )
