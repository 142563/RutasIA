# RutasIA — Sistema de Optimización de Rutas Inteligente

Sistema web de **optimización de rutas para empresas de paquetería en Guatemala**, considerando el tráfico en tiempo real. Propone la **ruta más rápida** usando **Dijkstra y A\*** implementados desde cero, sobre una **red vial nacional** cuyos tramos pesan **minutos** (no kilómetros), con datos de tráfico de **Google Maps**.

---

## Características principales

- **Motor de rutas nacional** (~100–150 nodos: cabeceras, municipios, cruces de carreteras)
  - Dijkstra y A\* con heurística Haversine (garantía de optimalidad)
  - Tráfico en 7 franjas horarias × 2 tipos de día (14 perfiles por arista)
  - Varias paradas: matriz de tiempos, vecino más cercano + 2-opt
  - Experimentos con métricas: nodos expandidos, tiempo, distancia, precisión

- **Aplicación React** moderna
  - Autenticación por roles: Administrador, Despachador, Conductor
  - Planificador de rutas: elegir criterio (tiempo o distancia)
  - Laboratorio visual: Dijkstra vs A\* lado a lado con animación
  - Pantalla de tráfico: franjas horarias y mejor hora para salir
  - Mapa esquemático de la red vial nacional (SVG)

- **API REST** en Django
  - Puntos de inicio: `/api/routing/route/`, `/api/routes/optimize/`, `/api/routing/compare/`
  - Trafico por franja: `/api/traffic/profile/`, `/api/routing/best_departure/`
  - Gestión de roles y autorización

- **Datos auditables**
  - Cada respuesta trae `data_source` (google, estimate, synthetic)
  - RouteSample: caché de consultas a Google Routes API
  - Permite auditar de dónde sale cada peso del grafo

---

## Arquitectura

### Django (backend)

```
logistics/
├── routing/              # Motor nuevo (docs/PLAN.md §2 y §5)
│   ├── graph.py          # RoadGraph: carga nodos y aristas en memoria, road_class, UNPAVED_SEGMENTS
│   ├── dijkstra.py       # Algoritmo punto-a-punto y uno-a-todos
│   ├── astar.py          # A* con heurística Haversine, v_max derivado de datos
│   ├── traffic.py        # Franjas horarias (7 × 2 = 14) y multiplicadores
│   ├── multistop.py      # Matriz + vecino cercano + 2-opt + ETAs
│   ├── incidents.py      # Penalización y bloqueo temporal de aristas
│   ├── build.py          # Construir grafo (Google Routes API)
│   ├── calibration.py    # Calibrar tráfico (Google Routes API, ~1 vez/semana)
│   ├── experiments.py    # E1–E7: correctitud, eficiencia, tráfico, precisión, paradas, hora, escalabilidad
│   ├── google.py         # Consultas a Routes API, con caché en BD
│   ├── geo.py            # Haversine sin redondeo, coordenadas
│   ├── synthetic.py      # Generar datos sintéticos para desarrollar
│   ├── instrument.py     # Instrumentación: nodos expandidos, tiempo, distancia
│   ├── seed_data.py      # Datos semilla: nodos iniciales de Guatemala
│   └── charts.py         # Gráficas para los experimentos (matplotlib)
├── domain/
│   ├── regions.py        # Regiones administrativas de Guatemala
│   └── exceptions.py     # PlanningError
├── application/
│   ├── routing.py        # Orquestación del motor nuevo (casos de uso)
│   ├── planning.py       # Planificador de rutas
│   ├── orders.py         # Gestión de pedidos
│   ├── incidents.py      # Reportar, procesar y recalcular con incidentes
│   ├── live_traffic.py   # Verificación en vivo con tráfico actual de Google
│   ├── fleet.py          # Configuración de bodegas, vehículos y conductores
│   ├── assignment.py     # Asignación y reasignación de rutas a conductores
│   └── demo.py           # Datos y ruta de ejemplo para demostración
├── presentation/
│   ├── routing_views.py  # Endpoints del motor nuevo (/api/routing/*, /api/routes/*)
│   ├── views.py          # Endpoints legacy
│   ├── app_views.py      # Vista SPA de React
│   └── serializers.py    # JSON (auth, roles, helpers)
└── models.py             # ORM: Node, Edge, TrafficProfile, Route, Order, Depot, ...
```

### React (frontend)

```
frontend/
├── src/
│   ├── pages/
│   │   ├── Home.tsx              # Resumen, accesos rápidos, mapa
│   │   ├── Login.tsx             # Autenticación
│   │   ├── planning/             # Planificador de rutas
│   │   ├── lab/                  # Laboratorio Dijkstra vs A*
│   │   ├── traffic/              # Tráfico por franja
│   │   └── driver/               # Vista del conductor (en desarrollo)
│   ├── components/
│   │   ├── map/NetworkMap.tsx    # Mapa SVG de la red vial
│   │   ├── ui/                   # shadcn/ui: botones, campos, etc.
│   │   └── layout/               # Shell de la aplicación
│   └── lib/
│       ├── api.ts                # Cliente HTTP a Django
│       ├── auth.tsx              # Context de autenticación
│       ├── queries.ts            # TanStack Query
│       ├── traffic.ts            # Cálculo de franjas horarias
│       └── planning.ts           # Lógica de planificación
```

### Base de datos

- PostgreSQL (Neon en producción, SQLite en desarrollo)
- Modelos nuevos: `Node`, `Edge` (dirigida), `TrafficProfile`, `RouteSample`, `Route`, `Depot`
- Modelos legacy: `Department`, `RouteConnection` (sigue funcionando)
- Auditoría: `data_source` en cada consulta

---

## Cómo levantarlo en tu compu

### Requisitos

- **Python** 3.12 o superior
- **Node.js** 20 o superior
- **Git**

### 1. Clonar y configurar entorno

```bash
git clone https://github.com/142563/RutasIA.git
cd RutasIA
git checkout dev

python -m venv .venv
# En Windows:
.venv\Scripts\activate
# En Linux/macOS:
source .venv/bin/activate

pip install -r requirements.txt
cp .env.example .env
```

### 2. Variables de entorno (`.env`)

Mínimo para empezar:
```bash
GOOGLE_MAPS_API_KEY=<tu-key-del-navegador>
DEBUG=true
SECRET_KEY=<generada-por-django>
```

Si dejas `DATABASE_URL` vacía, se usa SQLite local.

### 3. Preparación en un paso (recomendado)

```bash
python manage.py preparar [--google]
```

Este comando:
- Crea/actualiza la base de datos.
- Carga nodos y aristas del grafo nacional.
- Calibra tráfico (estimado o con Google Routes API).
- Compila la app React.
- Crea usuarios de demo (si `DEMO_PASSWORD` está en `.env`).
- Crea una ruta de ejemplo en curso.

**Usa `--google` solo si tienes `GOOGLE_ROUTES_API_KEY`** en `.env`. Sin ese flag, usa datos estimados (desarrollo rápido).

### 4. Comandos individuales (alternativa si necesitas control fino)

**Base de datos:**
```bash
python manage.py migrate
python manage.py seed_graph_nodes         # Nodos del grafo nacional
python manage.py createsuperuser          # Usuario admin
```

**Grafo y tráfico:**
```bash
# Sin Google (estimado):
python manage.py build_graph --estimate
python manage.py calibrate_traffic --synthetic

# Con Google (datos reales):
python manage.py build_graph
python manage.py calibrate_traffic
```

**Recalibración automática (semanal en producción):**
```bash
python manage.py refresh_traffic [--google]
```

**Archivado de pedidos viejos:**
```bash
python manage.py archive_legacy_orders [--apply]
```

### 5. Levantar Django

```bash
python manage.py runserver
```

Abre http://127.0.0.1:8000

### 6. Levantar React (desarrollo)

```bash
cd frontend
npm install
npm run dev
```

Abre http://localhost:5173 — Vite reenvía `/api` a Django en puerto 8000.

### 7. Correr pruebas

```bash
python manage.py test logistics      # Backend (Django)
cd frontend && npm test               # Frontend (Vitest)
```

---

## Usuarios de demo

Con `DEMO_PASSWORD` en `.env`:
```bash
python manage.py seed_demo_users
```

Se crean:
- **admin** / `<DEMO_PASSWORD>` — Administrador
- **despachador** / `<DEMO_PASSWORD>` — Planificador de rutas
- **conductor** / `<DEMO_PASSWORD>` — Entrega

---

## Experimentos (E1–E7)

Requiere `matplotlib` (en `requirements-dev.txt`):
```bash
pip install -r requirements-dev.txt
python manage.py run_experiments [--max-nodes 10000]
```

Genera CSV + PNG en `experiments/output/`:

| Experimento | Métrica | Resultado esperado |
|---|---|---|
| E1 | Correctitud | `costo(A*) == costo(Dijkstra)` en 100% de pares |
| E2 | Eficiencia | A\* expande ≤ nodos que Dijkstra, ganancia en viajes largos |
| E3 | Impacto tráfico | Ruta "rápida" vs "corta" por franja, cambios de carretera |
| E4 | Precisión (Should) | MAPE < 20% vs. Google en rutas completas |
| E5 | Varias paradas | 2-opt mejora vecino cercano |
| E6 | Hora salida (Should) | Curva de tiempo en 7 franjas |
| E7 | Escalabilidad | A\* en grafos de 1k–100k nodos |

---

## API REST (resumen)

Todos los endpoints requieren sesión autenticada. Ver `logistics/urls.py` y `logistics/presentation/routing_views.py`.

### Ruteo

| Método | Endpoint | Descripción |
|---|---|---|
| GET | `/api/routing/nodes/` | Nodos del grafo nacional |
| POST | `/api/routing/route/` | Ruta: origen, destino, hora, algoritmo (Dijkstra/A*), criterio (tiempo/km) |
| POST | `/api/routing/compare/` | Comparar algoritmos y criterios en una sola respuesta |
| POST | `/api/routes/optimize/` | Optimizar múltiples paradas: matriz, vecino cercano + 2-opt, ETAs |
| GET | `/api/routing/best_departure/` | Tiempo estimado en cada una de las 7 franjas horarias |
| GET | `/api/traffic/profile/` | Multiplicadores de tráfico (m ≥ 1) por arista, franja y tipo de día |

### Operaciones en vivo

| Método | Endpoint | Descripción |
|---|---|---|
| POST | `/api/incidents/` | Reportar incidente: tipo, ubicación, duración, multiplicador o bloqueo |
| GET | `/api/incidents/` | Listar incidentes activos |
| POST | `/api/routing/live-verify/` | Verificar ruta con tráfico actual de Google (RUT-39) |
| POST | `/api/routes/assign/` | Asignar ruta a conductor (RUT-35) |
| POST | `/api/routes/cancel/` | Cancelar asignación |

### Configuración (admin)

| Método | Endpoint | Descripción |
|---|---|---|
| GET/POST | `/api/fleet/depots/` | Bodegas |
| GET/POST | `/api/fleet/vehicles/` | Vehículos (camiones, motos) |
| GET/POST | `/api/fleet/drivers/` | Conductores con disponibilidad |
| POST | `/api/traffic/refresh/` | Ejecutar recalibración semanal (RUT-39) |

### Autenticación

| Método | Endpoint | Descripción |
|---|---|---|
| POST | `/api/auth/demo/` | Login rápido de demo (despachador o conductor) |
| POST | `/api/auth/logout/` | Cerrar sesión |
| GET | `/api/auth/me/` | Usuario actual |

---

## Flujo de trabajo (desarrollo)

### Rama y commits

- Rama principal: `dev` (se trabaja directamente en `dev` sin PR hasta producción)
- Antes de commit: `python manage.py test` en verde
- Mensaje de commit en español

### Reglas del motor (no negociables)

- Pesos **siempre ≥ 0** (tráfico multiplica, no resta)
- Costo y heurística en **misma unidad** (minutos)
- `v_max` **derivado de los datos**, no inventado
- Grafo **dirigido** y **en memoria** (sin consultas a BD dentro del bucle)
- Implementación propia con `heapq` (sin networkx, OR-Tools, OSMnx)
- Toda búsqueda devuelve instrumentación (nodos, ms, ruta)
- Prueba: `costo(A*) == costo(Dijkstra)` en todos los pares y franjas

Ver `CLAUDE.md` para arquitectura y convenciones completas.

---

## Diseño

- **Interfaz** y mensajes en **español**
- **Minimalista**: Geist + Geist Mono, neutros, negro `#111113` para acción principal
- **Color** solo para rutas, tráfico y estados
- Mapa esquemático (SVG), sin depender de Google Maps visual

---

## Deploy en Render

1. Crear Web Service en Render conectado al repositorio
2. **Build Command:**
   ```bash
   pip install -r requirements.txt && python manage.py collectstatic --noinput
   ```
3. **Start Command:**
   ```bash
   python manage.py migrate && gunicorn rutasia.wsgi:application --bind 0.0.0.0:$PORT --workers 3 --timeout 120
   ```
4. **Variables de entorno:** `GOOGLE_MAPS_API_KEY`, `DATABASE_URL` (Neon), `SECRET_KEY`

---

## Recursos

- **Plan completo:** [`docs/PLAN.md`](docs/PLAN.md)
- **Cómo empezar:** [`docs/EMPEZAR.md`](docs/EMPEZAR.md)
- **Keys de Google:** [`docs/GOOGLE_KEYS.md`](docs/GOOGLE_KEYS.md)
- **Trazabilidad protocolo:** [`docs/trazabilidad-objetivos.md`](docs/trazabilidad-objetivos.md)
- **Kanban de trabajo:** RUT en Kanban MCP (ver `/kanban`)

---

## Tecnologías

| Capa | Tecnología |
|---|---|
| Backend | Django 6, Python 3.12+, PostgreSQL (Neon) |
| Frontend | React 19, TypeScript, Vite, Tailwind v4, TanStack Query |
| Motor | Dijkstra, A*, Haversine, heapq (sin librerías de ruteo) |
| Datos viales | Google Routes API (construction), Google Maps API (dibujo) |
| Deploy | Render, WhiteNoise |

---

## Nota sobre datos

Mientras no se disponga de `GOOGLE_ROUTES_API_KEY`:
- Aristas: `source=estimate` (km y minutos estimados)
- Tráfico: `source=synthetic` (multiplicadores generados)

**Nunca presentar estos números como resultados de tesis.** La columna `data_source`
en cada respuesta audita el origen.

---

## Licencia

Proyecto académico — Universidad Mesoamericana de Guatemala.
