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
  - `logistics/domain/services.py` — Dijkstra (`RouteOptimizer`) y A\* (`AStarOptimizer`) sobre `Department`/`RouteConnection`.
  - `logistics/application/services.py` — `TripPlanner` y `TripLifecycleService` (casos de uso).
  - `logistics/presentation/views.py` — API JSON (`/api/...`) con sesión de Django + CSRF.
  - `templates/logistics/index.html` + `static/logistics/app.js` — frontend actual en JS sin framework (se reemplazará por React).
- BD: PostgreSQL (Neon) vía `DATABASE_URL`; sin esa variable usa SQLite local.
- Deploy: Render (`render.yaml`, `Procfile`), archivos estáticos con WhiteNoise.
- Pruebas: `python manage.py test` (3 pruebas, pasan).

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
- Rama de trabajo: `dev`. Cada funcionalidad en su propia rama desde `dev` y PR hacia `dev`. `main` = lo que está en producción.
- Antes de hacer commit: `python manage.py test` en verde.
