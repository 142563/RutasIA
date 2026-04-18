from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction

from logistics.models import Department, Driver, Order, RouteConnection, Vehicle


class Command(BaseCommand):
    help = "Carga datos de demostración para el sistema de rutas."

    @transaction.atomic
    def handle(self, *args, **options):
        departments_data = [
            ("GUA", "Guatemala", Decimal("14.634915"), Decimal("-90.506882")),
            ("SAC", "Sacatepéquez", Decimal("14.558571"), Decimal("-90.734306")),
            ("ESC", "Escuintla", Decimal("14.305000"), Decimal("-90.785000")),
            ("CHI", "Chimaltenango", Decimal("14.661111"), Decimal("-90.820000")),
            ("QUE", "Quetzaltenango", Decimal("14.845500"), Decimal("-91.518000")),
            ("RET", "Retalhuleu", Decimal("14.536111"), Decimal("-91.677778")),
            ("SUC", "Suchitepéquez", Decimal("14.534000"), Decimal("-91.363000")),
            ("PET", "Petén", Decimal("16.917000"), Decimal("-89.892000")),
            ("IZA", "Izabal", Decimal("15.728000"), Decimal("-88.594000")),
            ("ZAC", "Zacapa", Decimal("14.973000"), Decimal("-89.530000")),
        ]

        departments = {}
        for code, name, lat, lng in departments_data:
            department, _ = Department.objects.get_or_create(
                code=code,
                defaults={"name": name, "latitude": lat, "longitude": lng},
            )
            if department.name != name:
                department.name = name
                department.latitude = lat
                department.longitude = lng
                department.save(update_fields=["name", "latitude", "longitude"])
            departments[code] = department

        routes_data = [
            ("GUA", "SAC", Decimal("42.0")),
            ("GUA", "CHI", Decimal("55.0")),
            ("GUA", "ESC", Decimal("64.0")),
            ("SAC", "ESC", Decimal("52.0")),
            ("CHI", "QUE", Decimal("173.0")),
            ("ESC", "SUC", Decimal("101.0")),
            ("SUC", "RET", Decimal("47.0")),
            ("RET", "QUE", Decimal("62.0")),
            ("GUA", "ZAC", Decimal("147.0")),
            ("ZAC", "IZA", Decimal("98.0")),
            ("IZA", "PET", Decimal("304.0")),
            ("QUE", "PET", Decimal("402.0")),
            ("GUA", "PET", Decimal("506.0")),
        ]

        for origin_code, destination_code, distance in routes_data:
            RouteConnection.objects.get_or_create(
                origin=departments[origin_code],
                destination=departments[destination_code],
                defaults={"distance_km": distance, "is_bidirectional": True},
            )

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
            ("C-102BDF", "Camión Isuzu NPR",       Decimal("2800"), Decimal("6.5"), Decimal("4.10"), "GUA", "L-10234567"),
            ("C-215KLM", "Camión Hino 300",         Decimal("3500"), Decimal("5.9"), Decimal("4.60"), "ESC", "L-20987654"),
            ("P-883QRT", "Panel Hyundai H-1",       Decimal("1200"), Decimal("9.4"), Decimal("3.20"), "GUA", "L-30112233"),
            ("C-774RUV", "Camión Mitsubishi Fuso",  Decimal("3000"), Decimal("6.1"), Decimal("4.35"), "QUE", "L-40556677"),
        ]

        for plate, model, capacity, efficiency, cost, current, license_number in vehicles_data:
            Vehicle.objects.get_or_create(
                plate=plate,
                defaults={
                    "model": model,
                    "capacity_kg": capacity,
                    "fuel_efficiency_km_l": efficiency,
                    "cost_per_km": cost,
                    "is_active": True,
                    "current_department": departments[current],
                    "driver": drivers[license_number],
                },
            )

        if Order.objects.count() == 0:
            order_data = [
                ("GUA", "QUE", Decimal("850"), 24, Order.Priority.HIGH),
                ("GUA", "QUE", Decimal("600"), 12, Order.Priority.NORMAL),
                ("ESC", "RET", Decimal("430"), 18, Order.Priority.NORMAL),
                ("GUA", "PET", Decimal("500"), 8, Order.Priority.HIGH),
                ("GUA", "IZA", Decimal("300"), 10, Order.Priority.LOW),
            ]
            for origin_code, destination_code, weight, packages, priority in order_data:
                Order.objects.create(
                    origin=departments[origin_code],
                    destination=departments[destination_code],
                    weight_kg=weight,
                    package_count=packages,
                    priority=priority,
                    status=Order.Status.PENDING,
                )

        self.stdout.write(self.style.SUCCESS("Datos de demostración cargados correctamente."))
