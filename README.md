# RutasIA — Sistema de Optimización de Rutas Inteligente

**Producción: [https://enruta.world](https://enruta.world)** · Render · DNS en Spaceship · correos de entrega con Resend.

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
git clone https://github.com/142563/RutasIA.git RutasIA-Codex
cd RutasIA-Codex
git fetch origin
git checkout -b codex/rut-<n> origin/main

python -m venv .venv
# En Windows:
.venv\Scripts\activate
# En Linux/macOS:
source .venv/bin/activate

pip install -r requirements.txt
cp .env.example .env
```

### 2. Variables de entorno (`.env`)

Reemplaza `<n>` por tu tarjeta. Usa tu propia copia: la carpeta `C:\Users\Julio Ticas\Documents\Repositorios\RutasIA` está reservada para Claude. Copia `.env.example` a `.env`; nunca subas ese archivo ni secretos a Git.

| Variable | Uso | ¿Obligatoria? | Ejemplo sin secretos |
|---|---|---|---|
| `SECRET_KEY` | Sesiones Django | Sí en producción | `<clave privada aleatoria de al menos 50 caracteres>` |
| `DEBUG` | Detalles de errores | `False` en producción | `True` local / `False` Render |
| `ALLOWED_HOSTS` | Dominios aceptados | Sí para dominio propio | `enruta.world,www.enruta.world,rutasia.onrender.com` |
| `CSRF_TRUSTED_ORIGINS` | Orígenes HTTPS confiables | Configura los de producción | `https://enruta.world,https://www.enruta.world` |
| `DATABASE_URL` | PostgreSQL/Neon | Sí en Render; vacía usa SQLite | Vacío local / `<conexión privada de Neon>` |
| `GOOGLE_MAPS_API_KEY` | Mapa, Places, Directions del navegador | Solo para mapa Google | Vacío / `<key restringida por dominio>` |
| `GOOGLE_MAPS_MAP_ID` | Identificador del mapa | Opcional | `DEMO_MAP_ID` local |
| `GOOGLE_ROUTES_API_KEY` | Grafo y tráfico de Routes API | Solo para datos reales | Vacío / `<key privada del servidor>` |
| `DEMO_PASSWORD` | Creación de usuarios de demo | Solo para demo | `<contraseña propia>` |
| `DEMO_LOGIN` | Acceso sin contraseña despachador/conductor | Opcional; sigue `DEBUG` | `False` producción; `True` solo defensa autorizada |
| `RESEND_API_KEY` | Envío por Resend | Solo para enviar correo | Vacío local / `<key privada de Resend>` |
| `NOTIFY_FROM` | Remitente verificado | Opcional; valor por defecto | `enruta <entregas@enruta.world>` |
| `SITE_URL` | Enlace a la ruta en correos | Ajusta al entorno | `https://enruta.world` / `http://127.0.0.1:8000` local |

Para desarrollo usa los valores locales de `.env.example`, con `DATABASE_URL=` vacía. Sin keys Google hay mapa esquemático y datos estimados. En Render ingresa los secretos en **Environment**; `render.yaml` no declara `ALLOWED_HOSTS` ni `CSRF_TRUSTED_ORIGINS`, así que agrégalas en el panel del servicio web. [Guía completa de variables](docs/EMPEZAR.md#3-variables-de-entorno).

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
npm ci
npm run dev
```

Abre http://localhost:5173 — Vite reenvía `/api` a Django en puerto 8000.

### 7. Correr pruebas

```bash
pip install -r requirements-dev.txt
python -c 'import os,runpy,sys; os.environ["DATABASE_URL"]=""; sys.argv=["manage.py","test","--noinput"]; runpy.run_path("manage.py",run_name="__main__")'
cd frontend
npm ci
npx tsc -b
npx vitest run
npm run build
```

El comando del backend fuerza SQLite antes de leer `.env`; nunca corras pruebas contra la base de la nube. Las APIs Google y Resend se simulan en las pruebas.

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

### Rama y commits (regla de Julio, 2026-10-11)

- Trabaja en tu propia copia, en `codex/rut-<n>` desde `origin/main`.
- Antes del commit, completa todas las verificaciones de backend y frontend indicadas arriba.
- Commit en español, en imperativo y terminado en `(RUT-<n>)`.
- Actualiza documentación y kanban; deja la tarjeta en **En revision** e informa a Julio la rama y el hash. Claude revisa e integra a `main` localmente.
- **No hagas push, merge a main ni abras PR. Nadie hace push sin autorización de Julio**: cada push a `main` despliega automáticamente a producción.

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

El servicio existente publica **https://enruta.world**. Usa `render.yaml` como referencia: su build compila React con `npm ci` y `npm run build`, instala Python, ejecuta `collectstatic` y las migraciones; el inicio usa Gunicorn con tres workers. El cron `refresh-traffic` recalibra cada domingo a las 06:00 de Guatemala y necesita su conexión de Neon y key del servidor propias en Environment. Los valores privados se ingresan en Render, sin publicarlos en el repositorio.

### Dominio y DNS

En Spaceship, `A @` apunta a `216.24.57.1` (Render) y `CNAME www` a `rutasia.onrender.com`. Confirma los valores en **Custom Domains** de Render antes de reconfigurar; Render gestiona HTTPS. Para el correo, `TXT resend._domainkey` contiene la firma DKIM que entrega Resend (no se copia aquí); los CNAME `send` y `rsend` delegan SPF/Return-Path a `send.forge.rmta.net` y `rsend.forge.rmta.net`. `TXT _dmarc` con `v=DMARC1; p=none` monitorea, sin bloquear mensajes falsificados. Comprueba la verificación en ambos paneles: web y correo son servicios distintos.

Consulta [la tabla DNS y referencias oficiales](docs/EMPEZAR.md#dominio-y-dns), [Render](https://render.com/docs/custom-domains) y [Resend](https://resend.com/docs/dashboard/domains/custom-return-path). Los tipos y valores del panel de Resend prevalecen si cambia su configuración.

### Correos en local

Deja `RESEND_API_KEY=` vacía y `DATABASE_URL=` vacía. Con un pedido de prueba que tenga `cliente@example.invalid`, marca una parada como **Entregada** desde el conductor: se guarda la entrega y solo queda un registro `INFO` de los correos que no se enviaron; no hay llamada a Resend. El despachador creador también necesita correo para generar su aviso. Una parada fallida no dispara estos avisos. [Pasos para ver el log en consola](docs/EMPEZAR.md#probar-correos-en-local-sin-enviarlos).

Actualmente RUT-55 avisa de entregas al cliente y al despachador creador; los demás correos por rol de `PLAN.md` §14 siguen pendientes. No hace falta enviar correos reales para verificar el desarrollo.

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
