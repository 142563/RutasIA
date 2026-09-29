"""API JSON del motor de rutas nuevo (docs/PLAN.md §5, endpoints nuevos)."""
from __future__ import annotations

from django.contrib.auth.decorators import login_required
from django.http import HttpRequest
from django.views.decorators.http import require_GET, require_POST

from logistics.application import routing as service
from logistics.domain.exceptions import PlanningError
from logistics.presentation.serializers import _error, _ok, _parse_json


def _run(use_case, *args):
    try:
        return _ok(use_case(*args))
    except PlanningError as exc:
        return _error(str(exc))


@login_required
@require_GET
def api_routing_nodes(request: HttpRequest):
    return _run(service.nodes)


def _post(use_case):
    @login_required
    @require_POST
    def view(request: HttpRequest):
        try:
            payload = _parse_json(request)
        except PlanningError as exc:
            return _error(str(exc))
        return _run(use_case, payload)

    view.__name__ = f"api_{use_case.__name__}"
    return view


api_routing_route = _post(service.route)
api_routing_compare = _post(service.compare)
api_routing_explore = _post(service.explore)
api_routes_optimize = _post(service.optimize)


@login_required
@require_GET
def api_routing_best_departure(request: HttpRequest):
    return _run(service.best_departure, request.GET)


@login_required
@require_GET
def api_traffic_profile(request: HttpRequest):
    return _run(service.traffic_profile, request.GET)
