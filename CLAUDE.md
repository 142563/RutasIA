# CLAUDE.md

Guía para Claude Code en este repositorio. **Léela completa antes de programar.**

## Qué es este proyecto

Proyecto de graduación: sistema web de **optimización de rutas para empresas de paquetería en Guatemala**.
El objetivo es **proponer la mejor ruta considerando el tráfico**: un **algoritmo genético** propio ordena las paradas y
**Dijkstra y A\*** (también propios) calculan la matriz y cada tramo sobre una **red vial nacional** cuyas aristas pesan
**minutos** (no km). Los datos de tráfico vienen de Google Maps.

- **La tesis aprobada (PG2, Caps. I–V) es la especificación (2026-10-14):** si el código y el documento difieren, se
  corrige el código. Genético = motor principal; OR-Tools = solo línea base en experimentos; refuerzo con TensorFlow =
  exploratorio, en `experiments/colab/`.

- **Plan completo (fuente de verdad):** [`docs/PLAN.md`](docs/PLAN.md). Antes de una tarea, lee la sección que corresponda.
- **Foco (2026-10-10):** el producto es el **ruteo inteligente en vivo** (el sistema controla el mapa y decide la mejor ruta con tráfico), **no** un gestor de bodegas. Visión, avisos por rol y trabajo con Codex: §14 de `docs/PLAN.md`.
- **Prototipo de diseño:** [`docs/prototipo/`](docs/prototipo/README.md) (pantallas de referencia, estilo minimalista).
- **Cómo levantar el proyecto en tu compu:** [`docs/EMPEZAR.md`](docs/EMPEZAR.md).

## Estado actual del código

- Django 6 (requiere **Python ≥ 3.12**), app única `logistics`, organizada por capas:
  - **Motor nuevo** `logistics/routing/` (Semana 1, Días 1–5):
    - `graph.py` (`RoadGraph` en memoria), `dijkstra.py`, `astar.py` (`v_max` derivado de los datos), `instrument.py`.
    - `traffic.py` (franjas), `multistop.py` (matriz con Dijkstra + orden con el **genético** + tramos con A\* + ETAs).
    - `genetic.py` (RUT-79): algoritmo genético propio (torneo, cruce OX, mutación, elitismo, 2-opt memético), aptitud
      dependiente del tiempo (cada tramo con la franja en que empieza), semilla fija, sembrado con vecino más cercano +
      2-opt (nunca peor). Parámetros del administrador en `OptimizerSettings` (fila única, editable en `/admin/`).
    - `baseline_ortools.py` + `thesis_experiment.py`: experimento de la tesis (`python manage.py run_thesis_experiment`,
      3 escenarios × 10 repeticiones, convencional = proximidad sucesiva) con salida en `docs/Capitulo V/resultados/`.
      OR-Tools, SciPy y Pandas están solo en `requirements-dev.txt`.
    - `google.py` (Routes API, solo en comandos), `build.py`, `calibration.py`.
    - `experiments.py`, `synthetic.py`, `charts.py`, y los datos semilla en `seed_data.py`.
  - Modelos del grafo: `Node`, `Edge` (dirigida), `TrafficProfile` (m ≥ 1) y `RouteSample` (caché/bitácora de Google).
  - **Arranque en un paso:** `python manage.py preparar [--google]` (migra, nodos, tramos, tráfico, datos y usuarios de demo, compila React). Es idempotente y nunca reemplaza datos de Google por estimados. Explicación para humanos: `docs/COMO_FUNCIONA.md`.
  - Comandos sueltos: `seed_graph_nodes` → `build_graph [--estimate]` → `calibrate_traffic [--synthetic]` → `run_experiments`.
  - `logistics/application/routing.py` + `logistics/presentation/routing_views.py`: `/api/routing/*`, `/api/routes/optimize/`, `/api/traffic/profile/`.
  - **Motor y interfaz viejos retirados (RUT-40):** ya no existen `/clasico/`, `domain/services.py`, `application/services.py` ni los endpoints `/api/drivers/`, `/api/orders/`, `/api/trips/*`, etc. Los modelos `Department`, `RouteConnection`, `Trip`, `TripOrder`, `TripEvent` y `FuelPrice` se conservan (datos históricos, sin migración que los borre) pero ningún código nuevo los usa. `python manage.py archive_legacy_orders [--apply]` cancela los pedidos abiertos que dejó la interfaz vieja.
  - **App React** en `frontend/` (Vite + React 19 + TS + Tailwind v4 + componentes estilo shadcn en `src/components/ui`, React Router, TanStack Query). Mapa en `src/components/map/NetworkMap.tsx`: con `GOOGLE_MAPS_API_KEY` usa **Google Maps de fondo** (cargado en `src/lib/googleMaps.ts` con la key de `/api/config/`) y dibuja encima, en SVG, las capas del motor. Las rutas con `followRoads` se trazan por carretera real con Directions, pasando por los nodos que eligió nuestro algoritmo. Sin key, o si Google la rechaza, cae al mapa esquemático propio. Django la sirve desde `frontend/dist/app/` en `/` (vista `spa`); sesión por `/api/auth/*`.
  - Roles: `admin`, `dispatcher`, `driver` (`UserProfile.Role`); usuarios de demo con `seed_demo_users` (exige `DEMO_PASSWORD`).
  - **UX simple (prioridad del proyecto):**
    - Menú de 5 secciones: **Hoy** (inicio + monitoreo en vivo + "siguiente paso", `src/lib/today.ts`), **Pedidos**, **Planificar**, **Rutas** y **Análisis** (Laboratorio, Tráfico y Reportes en pestañas bajo `/analisis/*`; las rutas viejas redirigen).
    - Planificar por **zona**: los pedidos traen `region` (8 regiones oficiales, `logistics/domain/regions.py`) y `src/lib/zones.ts` los agrupa. El vehículo y el conductor se sugieren según la carga.
    - Login de un clic como despachador o conductor (`/api/auth/demo/`, activo con `DEMO_LOGIN`; por defecto igual a `DEBUG`; nunca para admin).
    - `preparar` crea una ruta de ejemplo en curso (`logistics/application/demo.py`).
    - La jerga técnica (nodos, multiplicadores, fuentes de datos) va en Análisis o en `<details>` plegados, no en las pantallas operativas.
- **Notificaciones (RUT-55):** al marcar una parada ENTREGADA, `logistics/application/notifications.py` envía correo con la API HTTP de Resend (`httpx`) al cliente (`Order.recipient_email`) y al despachador (`Route.created_by.email`), vía `transaction.on_commit` y sin romper nunca la entrega. Sin `RESEND_API_KEY` solo registra un log. Las entregas fallidas no envían nada. Los usuarios de demo no tienen correo.
- **Datos:** mientras no haya `GOOGLE_ROUTES_API_KEY`, el grafo usa aristas `estimate` y tráfico `synthetic`. Toda respuesta y todo CSV indica la fuente (`data_source`). **Nunca** presentar esos números como resultados de tesis.
- BD: PostgreSQL (Neon) vía `DATABASE_URL`; sin esa variable usa SQLite local.
- Deploy: Render (`render.yaml`, `Procfile`), archivos estáticos con WhiteNoise. `matplotlib` solo en `requirements-dev.txt`.
- Pruebas: `python manage.py test` (~70 s; `matplotlib` de requirements-dev.txt para las de gráficas; incluye E1 completa en `logistics/tests/test_search.py`).

## Hacia dónde vamos (resumen de docs/PLAN.md)

1. **Semana 1 — Motor de rutas** (prioridad absoluta), en `logistics/routing/`:
   - Grafo nacional de ~100–150 nodos (`Node`, `Edge` dirigidas) verificado con Google Routes API.
   - Costo de arista = `t0_e × m_e(franja, tipo_de_día)`, con `m ≥ 1`. Hay 7 franjas horarias × laboral/fin de semana.
   - Dijkstra (punto a punto y uno-a-todos) y A\* con `h(n) = haversine(n, destino) / v_max`, **`v_max` derivado de los datos**.
   - Varias paradas: matriz con Dijkstra, orden con el algoritmo genético, tramos con A\*.
   - Experimentos E1–E7 con `python manage.py run_experiments`.
2. **Semana 2 — App React** (`frontend/`: Vite + TypeScript + Tailwind + shadcn/ui). Django sirve la API y el build.
3. **Semana 3 — Conductor, incidentes y recálculo, pulido y deploy.**

## Reglas del motor de rutas (no negociables)

- Pesos **siempre ≥ 0**: el tráfico **multiplica** por ≥ 1, nunca resta.
- Costo y heurística en la **misma unidad** (minutos).
- `v_max = max_e haversine(u,v) / costo_mínimo(e)`. Así la heurística es admisible y consistente. Nunca uses una velocidad promedio.
- Grafo **dirigido** y cargado **en memoria**. **Nunca** llamar a Google ni a la BD dentro del bucle de Dijkstra o A\*.
- Implementación propia con `heapq` y biblioteca estándar (Dijkstra, A\* y el genético). **No** usar librerías de ruteo
  ni de optimización (networkx, OSMnx, DEAP, OR-Tools) en el motor ni en la API. **OR-Tools se permite solo como línea
  base** del experimento de la tesis (`baseline_ortools.py`, `requirements-dev.txt`; Render no lo instala).
- El genético usa la **misma** matriz de Dijkstra y respeta la terracería (se evita por defecto, ×20). Límite: 50 paradas
  y respuesta < 30 s (`response_seconds` en la API).
- Toda búsqueda devuelve instrumentación: nodos expandidos, ms y la ruta.
- Prueba obligatoria: `costo(A*) == costo(Dijkstra)` en todos los pares y franjas.
- Pruebas del genético: óptimo de fuerza bruta con 8 paradas, nunca peor que vecino más cercano + 2-opt, misma semilla =
  mismo resultado, 50 paradas < 30 s.

## Google Maps

- Key del **navegador** (`GOOGLE_MAPS_API_KEY`): mapa, Places, dibujo con Directions. Restringida por HTTP referrer.
- Key del **servidor** (`GOOGLE_ROUTES_API_KEY`, nueva): Routes API para construir el grafo y calibrar el tráfico. Se usa en comandos por lotes, con caché en BD.
- No leer datos de la capa visual de tráfico (condiciones de uso). Solo APIs de rutas.

## Convenciones

- Interfaz y mensajes al usuario en **español**. Código (nombres) en inglés y comentarios en español, como el código existente.
- Mantener la arquitectura por capas (domain / application / presentation).
- Diseño según §9 de `docs/PLAN.md` y `design-system/enruta/MASTER.md` (rediseño RUT-44):
  - Geist + Geist Mono. Tokens claro/oscuro en `frontend/src/index.css`; nunca hex sueltos (`bg-ink text-on-ink` para la acción principal).
  - Neutros con acento azul y naranja de entrega; el color sigue reservado para rutas, tráfico y estados.
  - Animaciones con Motion vía `src/components/ui/motion.tsx`, respetando "reducir movimiento".
  - Skill de diseño instalada: `.claude/skills/ui-ux-pro-max` (úsala para decisiones de UI).
- Nunca commitear `.env`, keys ni la `DATABASE_URL`. Usa `.env.example` como plantilla.
- **Seguridad (prioridad, §15 de `docs/PLAN.md`):** roles verificados en el backend, datos mínimos hacia afuera, nada de contraseñas ni cuerpos de correo en logs. Todo cambio que toque seguridad actualiza la tabla de `docs/SEGURIDAD.md` en el mismo commit.
- Rama de trabajo: `dev`. **Mientras no haya deploy a producción, se trabaja directo en `dev`, sin pull requests**: pruebas en verde → commit → push a `dev`. Cuando el proyecto esté en producción, cada funcionalidad irá en su rama desde `dev` con PR hacia `dev`. `main` = lo que está en producción.
- Antes de hacer commit: `python manage.py test` en verde (con `DATABASE_URL=` vacío para usar SQLite).
- **Codex** también trabaja en el repo, en su propia copia (nunca en la carpeta de Claude): tarjetas con etiqueta Codex en el kanban, rama `codex/rut-<n>` desde `main`, nunca merge directo; la tarjeta queda en "En revision" y Claude integra.
- **Push:** todo se integra con commit a `main`, pero **nadie hace push sin permiso de Julio** (Render despliega cada push a producción).
