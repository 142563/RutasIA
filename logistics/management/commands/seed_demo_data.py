from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction

from logistics.models import Depot, Driver, Node, Order, Vehicle
from logistics.routing.graph import invalidate_graph, load_graph


class Command(BaseCommand):
    help = "Carga datos de demostración para el sistema de rutas."

    @transaction.atomic
    def handle(self, *args, **options):
        drivers_data = [
            ("Carlos Andrés Mendoza López",   "5521-3344", "L-10234567"),
            ("Rosa María López Cifuentes",    "4433-2211", "L-20987654"),
            ("Miguel Ángel Fuentes Soto",     "3399-8877", "L-30112233"),
            ("Patricia Alejandra Ruiz Mora",  "5577-6612", "L-40556677"),
        ]

        drivers = {}
        for name, phone, license_number in drivers_data:
            driver, _ = Driver.objects.get_or_create(
                license_number=license_number,
                defaults={"name": name, "phone": phone, "is_active": True},
            )
            drivers[license_number] = driver

        vehicles_data = [
            ("C-102BDF", "Camión Isuzu NPR",       Decimal("2800"), Decimal("6.5"), Decimal("4.10"), "L-10234567"),
            ("C-215KLM", "Camión Hino 300",         Decimal("3500"), Decimal("5.9"), Decimal("4.60"), "L-20987654"),
            ("P-883QRT", "Panel Hyundai H-1",       Decimal("1200"), Decimal("9.4"), Decimal("3.20"), "L-30112233"),
            ("C-774RUV", "Camión Mitsubishi Fuso",  Decimal("3000"), Decimal("6.1"), Decimal("4.35"), "L-40556677"),
        ]

        for plate, model, capacity, efficiency, cost, license_number in vehicles_data:
            Vehicle.objects.get_or_create(
                plate=plate,
                defaults={
                    "model": model,
                    "capacity_kg": capacity,
                    "fuel_efficiency_km_l": efficiency,
                    "cost_per_km": cost,
                    "is_active": True,
                    "driver": drivers[license_number],
                },
            )

        self.seed_app_data()
        self.stdout.write(self.style.SUCCESS("Datos de demostración cargados correctamente."))

    def seed_app_data(self):
        """Bodega y pedidos con dirección para la aplicación nueva (datos ficticios, is_demo=True)."""
        invalidate_graph()
        graph = load_graph()
        if graph.node_count == 0:
            self.stdout.write(self.style.WARNING(
                "Sin grafo vial: corre seed_graph_nodes para crear la bodega y los pedidos de la app nueva."))
            return

        def nearest(lat, lng):
            return Node.objects.get(code=graph.codes[graph.nearest_node(lat, lng)])

        depot_lat, depot_lng = 14.5965, -90.5370
        Depot.objects.get_or_create(
            name="Bodega Central",
            defaults={"address": "Calzada Aguilar Batres, zona 12 (demostración)", "latitude": depot_lat,
                      "longitude": depot_lng, "node": nearest(depot_lat, depot_lng)},
        )
        if Order.objects.filter(is_demo=True).exists():
            return
        nodes = {n.code: n for n in Node.objects.all()}
        demo_orders = [
            ("Lucía Morales", "12 calle 3-40, zona 1", "chimaltenango", "4.5", 1, "normal"),
            ("Distribuidora El Roble", "Calzada Roosevelt 22-43", "mixco", "38.0", 6, "high"),
            ("Mario Chávez", "6a avenida 1-25, zona 4", "quetzaltenango", "2.1", 1, "normal"),
            ("Farmacia San Rafael", "7a avenida 14-52", "retalhuleu", "12.6", 3, "high"),
            ("Sofía Ramírez", "20 calle 10-15", "escuintla", "1.3", 1, "low"),
            ("Óscar Lemus", "Boulevard principal 18-80", "antigua-guatemala", "6.8", 2, "normal"),
            ("Taller Hermanos Cux", "4a calle 8-20", "totonicapan", "54.0", 4, "normal"),
            ("Andrea Solís", "13 avenida 5-66", "coban", "3.2", 1, "normal"),
            ("Librería Cervantes", "9a calle 6-12", "zacapa", "22.4", 5, "normal"),
            ("Ricardo Tzul", "Avenida central 45-10", "solola", "9.9", 2, "high"),
            ("Ferretería La Estrella", "3a avenida 2-31", "huehuetenango", "41.0", 8, "normal"),
            ("Comercial Petén", "Calle Centroamérica 5-20", "flores", "15.5", 3, "high"),
            ("Clínica Santa Ana", "2a calle 7-45", "jutiapa", "7.2", 2, "normal"),
            ("Abarrotería Doña Tere", "Barrio El Centro", "mazatenango", "18.0", 4, "low"),
            ("Café Las Nubes", "Km 1 salida a Salamá", "salama", "11.0", 2, "normal"),
            ("Agroservicio El Sembrador", "1a avenida 3-10", "chiquimula", "33.0", 5, "normal"),
            ("Hotel Puerto Azul", "6a avenida y 10 calle", "puerto-barrios", "25.0", 3, "normal"),
            ("Panificadora San José", "5a calle 4-22", "san-marcos", "8.4", 2, "normal"),
            ("Escuela Rural Mixta", "Aldea El Rancho", "el-rancho", "19.0", 3, "low"),
            ("Tienda Don Beto", "Calle real 12-01", "cuilapa", "5.6", 1, "normal"),
        ]
        for i, (recipient, address, code, weight, packages, priority) in enumerate(demo_orders):
            node = nodes.get(code)
            if node is None:
                continue
            # Pequeño desplazamiento para que la dirección no caiga exactamente en el nodo
            lat, lng = node.latitude + 0.004 * ((i % 3) - 1), node.longitude + 0.004 * ((i % 2) * 2 - 1)
            Order.objects.create(
                recipient=recipient, address=f"{address}, {node.name}", reference="Pedido de demostración",
                latitude=lat, longitude=lng, node=nearest(lat, lng), weight_kg=Decimal(weight),
                package_count=packages, priority=priority, status=Order.Status.PENDING, is_demo=True,
            )
        self.stdout.write(f"Pedidos de demostración con dirección: {len(demo_orders)}")
