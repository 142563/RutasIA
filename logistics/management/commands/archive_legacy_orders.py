"""Archiva los pedidos que dejó la interfaz anterior (/clasico/, ya retirada).

Sin --apply solo muestra cuáles son. Con --apply los pasa a "Cancelado" y deja
constancia en el campo `reference`; nunca borra nada.
"""
from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import Q

from logistics.application.orders import app_orders
from logistics.models import Order

MARK = "[Archivado: pedido de la interfaz anterior]"
TERMINAL = (Order.Status.DELIVERED, Order.Status.FAILED, Order.Status.CANCELED)


def legacy_orders():
    """Pedidos viejos que siguen abiertos.

    Viejo = no pertenece a la app nueva (sin ubicación de entrega) o está
    asignado / en ruta sin ninguna parada de ruta. Los ya terminados
    (entregado, no entregado, cancelado) son historia y no se tocan.
    """
    new_app_ids = app_orders().values("id")
    stuck = Q(status__in=[Order.Status.ASSIGNED, Order.Status.IN_TRANSIT], route_stops__isnull=True)
    return (Order.objects.exclude(status__in=TERMINAL)
            .filter(~Q(id__in=new_app_ids) | stuck)
            .distinct().order_by("id"))


class Command(BaseCommand):
    help = "Archiva (cancela, sin borrar) los pedidos abiertos de la interfaz anterior. Usa --apply para aplicarlo."

    def add_arguments(self, parser):
        parser.add_argument("--apply", action="store_true", help="Aplica el archivado (por defecto solo lista).")

    def handle(self, *args, apply=False, **options):
        orders = list(legacy_orders())
        self.stdout.write(f"Pedidos viejos abiertos: {len(orders)}")
        for o in orders:
            self.stdout.write(f"  {o.code}  {o.get_status_display():<10}  {o.recipient or o}")
        if not orders:
            return
        if not apply:
            self.stdout.write("Es solo una vista previa: agrega --apply para archivarlos.")
            return
        with transaction.atomic():
            for o in orders:
                o.status = Order.Status.CANCELED
                o.reference = f"{MARK} {o.reference}".strip()[:255]
                o.save(update_fields=["status", "reference", "updated_at"])
        self.stdout.write(self.style.SUCCESS(f"Archivados: {len(orders)}"))
