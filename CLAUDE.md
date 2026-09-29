# CLAUDE.md

Guía para Claude Code en este repositorio. **Léela completa antes de programar.**

## Qué es este proyecto

Proyecto de graduación: sistema web de **optimización de rutas para empresas de paquetería en Guatemala**.
El objetivo es **proponer la mejor ruta considerando el tráfico**, usando **Dijkstra y A\*** implementados por nosotros
sobre una **red vial nacional** cuyas aristas pesan **minutos** (no km). Los datos de tráfico vienen de Google Maps.

- **Plan completo (fuente de verdad):** [`docs/PLAN.md`](docs/PLAN.md). Antes de una tarea, lee la sección que corresponda.
- **Prototipo de diseño:** [`docs/prototipo/`](docs/prototipo/README.md) (pantallas de referencia, estilo minimalista).
- **Cómo levantar el proyecto en tu compu:** [`docs/EMPEZAR.md`](docs/EMPEZAR.md).

## Estado actual del código

- Django 6 (requiere **Python ≥ 3.12**), app única `logistics`, organizada por capas:
  - **Motor nuevo** `logistics/routing/` (Semana 1, Días 1–5):
    - `graph.py` (`RoadGraph` en memoria), `dijkstra.py`, `astar.py` (`v_max` derivado de los datos), `instrument.py`.
    - `traffic.py` (franjas), `multistop.py` (matriz + vecino más cercano + 2-opt + ETAs).
    - `google.py` (Routes API, solo en comandos), `build.py`, `calibration.py`.
    - `experiments.py`, `synthetic.py`, `charts.py`, y los datos semilla en `seed_data.py`.
  - Modelos del grafo: `Node`, `Edge` (dirigida), `TrafficProfile` (m ≥ 1) y `RouteSample` (caché/bitácora de Google).
  - Comandos: `seed_graph_nodes` → `build_graph [--estimate]` → `calibrate_traffic [--synthetic]` → `run_experiments`.
  - `logistics/application/routing.py` + `logistics/presentation/routing_views.py`: `/api/routing/*`, `/api/routes/optimize/`, `/api/traffic/profile/`.
  - **Motor viejo** (sigue funcionando hasta que llegue React): `logistics/domain/services.py` (`RouteOptimizer`, `AStarOptimizer` sobre `Department`/`RouteConnection`), `logistics/application/services.py` (`TripPlanner`), `logistics/presentation/views.py`.
  - **App React** en `frontend/` (Vite + React 19 + TS + Tailwind v4 + componentes estilo shadcn en `src/components/ui`, React Router, TanStack Query). Mapa esquemático propio en SVG (`src/components/map/NetworkMap.tsx`), sin depender de Google. Django la sirve desde `frontend/dist/app/` en `/` (vista `spa`); sesión por `/api/auth/*`.
  - Interfaz anterior (JS sin framework) en `/clasico/`: `templates/logistics/index.html` + `static/logistics/app.js`.
  - Roles: `admin`, `dispatcher`, `driver` (`UserProfile.Role`); usuarios de demo con `seed_demo_users` (exige `DEMO_PASSWORD`).
- **Datos:** mientras no haya `GOOGLE_ROUTES_API_KEY`, el grafo usa aristas `estimate` y tráfico `synthetic`. Toda respuesta y todo CSV indica la fuente (`data_source`). **Nunca** presentar esos números como resultados de tesis.
- BD: PostgreSQL (Neon) vía `DATABASE_URL`; sin esa variable usa SQLite local.
- Deploy: Render (`render.yaml`, `Procfile`), archivos estáticos con WhiteNoise. `matplotlib` solo en `requirements-dev.txt`.
- Pruebas: `python manage.py test` (86 pruebas, ~30 s; incluye E1 completa en `logistics/tests/test_search.py`).

## Hacia dónde vamos (resumen de docs/PLAN.md)

1. **Semana 1 — Motor de rutas** (prioridad absoluta), en `logistics/routing/`:
   - Grafo nacional de ~100–150 nodos (`Node`, `Edge` dirigidas) verificado con Google Routes API.
   - Costo de arista = `t0_e × m_e(franja, tipo_de_día)`, con `m ≥ 1`. Hay 7 franjas horarias × laboral/fin de semana.
   - Dijkstra (punto a punto y uno-a-todos) y A\* con `h(n) = haversine(n, destino) / v_max`, **`v_max` derivado de los datos**.
   - Varias paradas: matriz con Dijkstra, vecino más cercano + 2-opt, tramos con A\*.
   - Experimentos E1–E7 con `python manage.py run_experiments`.
2. **Semana 2 — App React** (`frontend/`: Vite + TypeScript + Tailwind + shadcn/ui). Django sirve la API y el build.
3. **Semana 3 — Conductor, incidentes y recálculo, pulido y deploy.**

## Reglas del motor de rutas (no negociables)

- Pesos **siempre ≥ 0**: el tráfico **multiplica** por ≥ 1, nunca resta.
- Costo y heurística en la **misma unidad** (minutos).
- `v_max = max_e haversine(u,v) / costo_mínimo(e)`. Así la heurística es admisible y consistente. Nunca uses una velocidad promedio.
- **No redondear la heurística hacia arriba**. `haversine_km` usa hoy `ROUND_HALF_UP` (`logistics/domain/services.py:29`) y debe corregirse.
- Grafo **dirigido** y cargado **en memoria**. **Nunca** llamar a Google ni a la BD dentro del bucle de Dijkstra o A\*.
- Implementación propia con `heapq`. **No** usar librerías de ruteo (networkx, OR-Tools, OSMnx) en el motor.
- Toda búsqueda devuelve instrumentación: nodos expandidos, ms y la ruta.
- Prueba obligatoria: `costo(A*) == costo(Dijkstra)` en todos los pares y franjas.

## Google Maps

- Key del **navegador** (`GOOGLE_MAPS_API_KEY`): mapa, Places, dibujo con Directions. Restringida por HTTP referrer.
- Key del **servidor** (`GOOGLE_ROUTES_API_KEY`, nueva): Routes API para construir el grafo y calibrar el tráfico. Se usa en comandos por lotes, con caché en BD.
- No leer datos de la capa visual de tráfico (condiciones de uso). Solo APIs de rutas.

## Convenciones

- Interfaz y mensajes al usuario en **español**. Código (nombres) en inglés y comentarios en español, como el código existente.
- Mantener la arquitectura por capas (domain / application / presentation).
- Diseño **minimalista** según §9 de `docs/PLAN.md`:
  - Geist + Geist Mono.
  - Neutros; negro `#111113` para la acción principal; el color solo para rutas, tráfico y estados.
- Nunca commitear `.env`, keys ni la `DATABASE_URL`. Usa `.env.example` como plantilla.
- Rama de trabajo: `dev`. **Mientras no haya deploy a producción, se trabaja directo en `dev`, sin pull requests**: pruebas en verde → commit → push a `dev`. Cuando el proyecto esté en producción, cada funcionalidad irá en su rama desde `dev` con PR hacia `dev`. `main` = lo que está en producción.
- Antes de hacer commit: `python manage.py test` en verde.
