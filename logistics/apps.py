from django.apps import AppConfig


class LogisticsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "logistics"

    def ready(self):
        from django.db.models.signals import post_delete, post_save
        # Grafo nacional en memoria (motor nuevo)
        from logistics.models import Edge, Node, TrafficProfile
        from logistics.routing.graph import invalidate_graph

        def _invalidate_road_graph(sender, **kwargs):
            invalidate_graph()

        for model in (Node, Edge, TrafficProfile):
            post_save.connect(_invalidate_road_graph, sender=model, weak=False)
            post_delete.connect(_invalidate_road_graph, sender=model, weak=False)
