# JaironRoute — Sistema de Optimización de Rutas

Sistema web de gestión y optimización de rutas logísticas para Guatemala. Permite planificar viajes entre departamentos usando algoritmos de camino más corto, gestionar pedidos, conductores y vehículos, y visualizar rutas en un mapa interactivo.

---

## Descripción del proyecto

JaironRoute resuelve el problema de encontrar la ruta más corta entre cualquier par de departamentos de Guatemala, considerando las conexiones viales reales y sus distancias en kilómetros. El sistema:

- Calcula rutas óptimas usando el algoritmo de **Dijkstra** (grafo de distancias viales) o **A\*** (con heurística Haversine).
- Visualiza la ruta sobre un mapa vectorial con **MapLibre GL JS** y traza el trazado real por carreteras via **OpenRouteService**.
- Gestiona el ciclo de vida completo de un viaje: planificación → en progreso → completado / cancelado.
- Calcula costos estimados de combustible (GTQ/galón) y costo por kilómetro del vehículo.
- Controla acceso por roles: Administrador, Supervisor y Operador.

---

## Tecnologías utilizadas

| Capa | Tecnología |
|------|-----------|
| Backend | Python 3.13, Django 6.0 |
| Servidor WSGI | Gunicorn 22 |
| Archivos estáticos | WhiteNoise 6.7 |
| Base de datos | PostgreSQL (Neon serverless) |
| ORM | Django ORM + Django Cache Framework |
| Frontend | Vanilla JavaScript ES2022 |
| Mapa | MapLibre GL JS, OpenFreeMap (estilo Liberty — vector tiles) |
| Ruteo por carreteras | OpenRouteService API (preference=fastest) |
| Ruteo fallback | OSRM (Open Source Routing Machine) |
| Algoritmos | Dijkstra (camino más corto), A* con heurística Haversine |
| Deploy | Render.com (web service) |

---

## Cómo se consume cada tecnología

### 🐍 Django 6.0 — Framework web

Maneja el servidor HTTP, autenticación, base de datos y caché. Cada endpoint de la API es una función Django decorada:

```python
# logistics/urls.py
path("api/trips/plan/", views.api_plan_trip, name="api-plan-trip")

# logistics/presentation/views.py
@login_required               # redirige si no hay sesión activa
@require_http_methods(["POST"])
def api_plan_trip(request: HttpRequest):
    ...
```

---

### 🐘 PostgreSQL en Neon — Base de datos

Almacena departamentos, vehículos, viajes, precios de gasolina y toda la información operativa. Se accede exclusivamente a través del ORM de Django:

```python
# logistics/domain/services.py — consulta para construir el grafo de Dijkstra
RouteConnection.objects.only("origin_id", "destination_id", "distance_km", "is_bidirectional")

# logistics/application/services.py — guarda un viaje nuevo
Trip.objects.create(vehicle=vehicle, route_nodes=route_nodes, ...)

# .env — cadena de conexión
DATABASE_URL=postgresql://neondb_owner:...@neon.tech/neondb?sslmode=require
```

---

### ⚡ Django Cache Framework — Caché en memoria

Guarda el grafo de Dijkstra 2 minutos para no consultar la base de datos en cada cálculo de ruta:

```python
# logistics/domain/services.py
def _build_graph():
    cached = cache.get("dijkstra_graph_v1")    # busca en memoria primero
    if cached is not None:
        return cached                           # responde sin tocar la BD
    # ... construye grafo desde RouteConnection en BD ...
    cache.set("dijkstra_graph_v1", result, 120)  # guarda 120 segundos
    return result
```

---

### 🗺️ MapLibre GL JS — Motor del mapa

Renderiza el mapa interactivo en el navegador con capas vectoriales (puntos, líneas, etiquetas):

```javascript
// static/logistics/app.js
map = new maplibregl.Map({
    container: "route-map",
    style: "https://tiles.openfreemap.org/styles/liberty",  // estilo vectorial
    center: [-90.3, 15.45],   // Guatemala
    zoom: 7
});

// Agrega los departamentos como puntos interactivos
map.addLayer({ id: "departments-layer", type: "circle", source: "departments-source" });

// Dibuja la ruta óptima resaltada en naranja
map.addLayer({ id: "highlight-line-layer", type: "line", source: "highlight-source" });
```

---

### 🌍 OpenFreeMap Liberty — Tiles vectoriales del mapa

Provee los mapas vectoriales (calles, ríos, nombres, pueblos) sin costo ni API key. Reemplazó 30 líneas de configuración raster de Esri:

```javascript
// Una sola URL carga el estilo completo: colores, tipografías, capas
style: "https://tiles.openfreemap.org/styles/liberty"
```

---

### 🛣️ OpenRouteService (ORS) — Geometría de carreteras reales

Dado un conjunto de puntos GPS (departamentos en la ruta), devuelve cientos de coordenadas que forman la carretera real. `preference: "fastest"` elige autopistas sobre caminos viejos:

```javascript
// static/logistics/app.js — función _fetchViaORS()
fetch("https://api.openrouteservice.org/v2/directions/driving-car/geojson", {
    method: "POST",
    headers: {
        "Authorization": "Bearer " + window.ORS_API_KEY   // JWT token
    },
    body: JSON.stringify({
        coordinates: [[lon1, lat1], [lon2, lat2]],   // waypoints del viaje
        preference: "fastest"    // elige autopista CA-9 sobre carretera vieja
    })
})
// Respuesta: 300+ coordenadas siguiendo la carretera exacta en el mapa
```

Si ORS falla, el sistema cae automáticamente al fallback OSRM:

```javascript
async function fetchRoadGeometry(waypointCoords) {
    if (window.ORS_API_KEY) {
        try { return await _fetchViaORS(waypointCoords); }
        catch (err) { console.warn("ORS no disponible, usando OSRM:", err.message); }
    }
    return _fetchViaOSRM(waypointCoords);   // fallback automático
}
```

---

### 📐 Dijkstra — Algoritmo de ruta óptima

Decide qué departamentos atravesar (ej: Guatemala → Escuintla → Quetzaltenango) operando sobre las distancias reales de carretera almacenadas en `RouteConnection`:

```python
# logistics/domain/services.py — clase RouteOptimizer
while queue:
    g, node = heapq.heappop(queue)        # saca el nodo más cercano (min-heap)
    for neighbor, weight in graph.get(node, []):
        candidate = g + weight            # distancia acumulada candidata
        if candidate < distances.get(neighbor, INF):
            distances[neighbor] = candidate
            heapq.heappush(queue, (candidate, neighbor))
```

---

### 🔢 Haversine — Heurística geográfica para A*

Calcula la distancia en línea recta entre dos coordenadas GPS. La usa internamente A* para descartar rutas que van en dirección equivocada:

```python
# logistics/domain/services.py
def haversine_km(lat1, lon1, lat2, lon2):
    R = 6371.0                            # radio de la Tierra en km
    a = math.sin(dphi/2)**2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda/2)**2
    return 2 * R * math.asin(math.sqrt(a))   # distancia en km

# Usada en A* como:  f(n) = g(n) + haversine_km(n, destino)
```

---

### 🔄 Flujo completo de un viaje planificado

```
Usuario hace click "Planificar"
        │
        ▼
app.js  →  POST /api/trips/plan/              (JavaScript en el navegador)
        │
        ▼
presentation/views.py  →  api_plan_trip()     (Django recibe la petición HTTP)
        │
        ▼
application/services.py  →  TripPlanner       (orquesta el caso de uso)
        │
        ▼
domain/services.py  →  RouteOptimizer         (Dijkstra calcula la ruta)
        │
        ▼
RouteConnection en PostgreSQL/Neon            (distancias reales desde BD)
        │
        ▼
Trip guardado con precio de gasolina actual   (FuelPrice.current())
        │
        ▼
app.js recibe la respuesta JSON
        │
        ▼
_fetchViaORS()  →  OpenRouteService API       (geometría de carretera real)
        │
        ▼
MapLibre GL dibuja la ruta sobre OpenFreeMap  (mapa vectorial en pantalla)
```

---

## Arquitectura DDD (Domain-Driven Design)

El código dentro de `logistics/` está organizado en cuatro capas con responsabilidades separadas:

```
+----------------------------------------------------------+
|  Presentation Layer   (logistics/presentation/)          |
|  HTTP handlers, JSON serializers, decoradores de vista   |
+----------------------------------------------------------+
|  Application Layer    (logistics/application/)           |
|  Casos de uso: TripPlanner, TripLifecycleService         |
+----------------------------------------------------------+
|  Domain Layer         (logistics/domain/)                |
|  Logica de negocio pura: RouteOptimizer, AStarOptimizer  |
|  Entidades de dominio, excepciones (PlanningError)       |
+----------------------------------------------------------+
|  Infrastructure       (logistics/models.py + cache)      |
|  Django ORM, Django Cache Framework, APIs externas       |
|  (OpenRouteService / OSRM)                               |
+----------------------------------------------------------+
```

### Descripcion de capas

**Presentation Layer** (`logistics/presentation/`)
- `views.py` — Funciones de vista Django con decoradores de autenticacion y metodo HTTP.
- `serializers.py` — Helpers `_serialize_*()` que convierten instancias de modelo a dicts JSON, mas utilidades `_ok()`, `_error()`, `_parse_json()` y control de roles.

**Application Layer** (`logistics/application/`)
- `services.py` — Orquesta los casos de uso de negocio. `TripPlanner.plan_trip()` coordina la validacion, el algoritmo de ruteo, el calculo de costos y la persistencia. `TripLifecycleService` controla las transiciones de estado del viaje.

**Domain Layer** (`logistics/domain/`)
- `services.py` — Algoritmos puros de grafos (`RouteOptimizer`, `AStarOptimizer`), funcion `haversine_km()`, construccion y cacheo del grafo, constantes de dominio.
- `exceptions.py` — `PlanningError`, excepcion base para todos los errores de logica de negocio.

**Infrastructure**
- `logistics/models.py` — Modelos Django (no se mueven; las migraciones dependen de su ubicacion).
- Cache de Django — El grafo de conexiones y las coordenadas de departamentos se cachean 120 segundos.
- APIs externas — OpenRouteService y OSRM se consumen desde el frontend JavaScript, no desde el backend Python.

---

## Modelos de datos

| Modelo | Descripcion |
|--------|-------------|
| `Department` | Departamento de Guatemala con codigo, nombre y coordenadas GPS. |
| `RouteConnection` | Conexion vial entre dos departamentos con distancia en km (puede ser bidireccional). |
| `Vehicle` | Vehiculo con placa, modelo, capacidad, eficiencia de combustible y costo por km. |
| `Driver` | Conductor con nombre, telefono y numero de licencia. |
| `Order` | Pedido de envio con origen, destino, peso, prioridad y estado. |
| `Trip` | Viaje planificado que agrupa pedidos, calcula ruta y registra costos. |
| `FuelPrice` | Singleton con precios de combustible (regular, super, diesel) en GTQ/galón. |
| `TripEvent` | Bitacora de eventos asociados a un viaje (inicio, completado, notas). |
| `UserProfile` | Extension de `User` con rol (admin / supervisor / operador). |

---

## Algoritmos de ruteo

### Grafo interno — Dijkstra vs A*

Ambos algoritmos operan sobre un grafo en memoria construido a partir de los registros `RouteConnection` de la base de datos.

**Dijkstra** (`RouteOptimizer`)

Explora nodos en orden de distancia acumulada desde el origen. Garantiza el camino mas corto en grafos con pesos no negativos. Complejidad O((V + E) log V).

**A\*** (`AStarOptimizer`)

Guia la busqueda hacia el destino con una heuristica admisible que nunca sobreestima el costo real:

```
f(n) = g(n) + h(n)

donde:
  g(n) = distancia acumulada desde el origen hasta n  (coste real)
  h(n) = haversine_km(n, destino)                     (distancia en linea recta — heuristica admisible)
```

Al ser `h(n)` admisible (linea recta <= distancia vial), A* garantiza optimalidad y suele expandir menos nodos que Dijkstra.

**Por que Dijkstra es el predeterminado**

El grafo de Guatemala tiene pocos nodos (~22 departamentos) y pocas aristas, por lo que la diferencia de rendimiento es irrelevante en produccion. Dijkstra se usa por defecto por su simplicidad; A* esta disponible como opcion avanzada.

### Visualizacion en mapa — OpenRouteService

El grafo interno solo contiene distancias en km. Para dibujar la ruta sobre el mapa con curvas de carretera reales, el frontend llama a la API de **OpenRouteService** (profile `driving-car`, preference `fastest`). Si ORS falla, el frontend usa **OSRM** como fallback.

---

## Instalacion local

### Requisitos previos

- Python 3.13+
- PostgreSQL (o acceder a una base de datos Neon con `DATABASE_URL`)

### Pasos

```bash
# 1. Clonar el repositorio
git clone <repo-url>
cd RutasIA

# 2. Crear y activar entorno virtual
python -m venv .venv
source .venv/bin/activate      # Linux/macOS
.venv\Scripts\activate         # Windows

# 3. Instalar dependencias
pip install -r requirements.txt

# 4. Configurar variables de entorno (ver seccion siguiente)
# Crear .env en la raiz del proyecto

# 5. Aplicar migraciones
python manage.py migrate

# 6. Cargar datos de demostracion (departamentos, conexiones, usuario admin)
python manage.py seed_demo_data

# 7. Iniciar servidor de desarrollo
python manage.py runserver
```

Abrir http://127.0.0.1:8000/ en el navegador. Credenciales por defecto: `admin` / `admin123`.

---

## Variables de entorno

Crear un archivo `.env` en la raiz del proyecto:

| Variable | Descripcion | Ejemplo |
|----------|-------------|---------|
| `DATABASE_URL` | URL de conexion PostgreSQL (Neon o local) | `postgresql://user:pass@host/db` |
| `SECRET_KEY` | Clave secreta de Django | `django-insecure-...` |
| `DEBUG` | Modo depuracion (`true` / `false`) | `false` |
| `ALLOWED_HOSTS` | Hosts permitidos, separados por coma | `localhost,mi-app.onrender.com` |
| `ORS_API_KEY` | API key de OpenRouteService | `5b3ce3597851...` |

---

## Estructura del proyecto

```
RutasIA/
|-- manage.py
|-- requirements.txt
|-- README.md
|
|-- rutasia/                        # Configuracion del proyecto Django
|   |-- settings.py
|   |-- urls.py
|   `-- wsgi.py
|
`-- logistics/                      # Aplicacion principal
    |-- models.py                   # Modelos Django (Infrastructure)
    |-- admin.py
    |-- apps.py
    |-- tests.py
    |-- urls.py                     # Enrutamiento URL
    |-- views.py                    # Re-export de compatibilidad hacia atras
    |-- services.py                 # Re-export de compatibilidad hacia atras
    |
    |-- domain/                     # Domain Layer — logica de negocio pura
    |   |-- __init__.py
    |   |-- exceptions.py           # PlanningError
    |   `-- services.py             # RouteOptimizer, AStarOptimizer, haversine_km, constantes
    |
    |-- application/                # Application Layer — casos de uso
    |   |-- __init__.py
    |   `-- services.py             # TripPlanner, TripLifecycleService
    |
    |-- presentation/               # Presentation Layer — HTTP / JSON
    |   |-- __init__.py
    |   |-- serializers.py          # _serialize_*, _ok, _error, _parse_json, helpers de rol
    |   `-- views.py                # Todas las funciones de vista Django
    |
    |-- migrations/                 # Migraciones de base de datos (no modificar)
    |   |-- 0001_initial.py
    |   |-- 0002_driver_trip_driver_vehicle_driver_userprofile.py
    |   `-- 0003_fuelprice_trip_estimated_fuel_cost_gtq_and_more.py
    |
    |-- templates/
    |   `-- logistics/
    |       `-- index.html
    |
    `-- static/
        `-- logistics/
            |-- app.js
            `-- styles.css
```

---

## API REST

Todos los endpoints requieren sesion autenticada. Base URL: `/`

| Metodo | Endpoint | Descripcion |
|--------|----------|-------------|
| GET | `/api/me/` | Datos del usuario autenticado |
| GET/POST | `/api/users/` | Listar / crear usuarios (admin) |
| GET | `/api/dashboard/` | Metricas y estadisticas |
| GET | `/api/departments/` | Listar departamentos |
| GET | `/api/connections/` | Listar conexiones viales |
| GET/POST | `/api/drivers/` | Listar / crear conductores |
| GET/POST | `/api/vehicles/` | Listar / crear vehiculos |
| GET/POST | `/api/orders/` | Listar / crear pedidos |
| GET | `/api/trips/` | Listar viajes |
| POST | `/api/trips/plan/` | Planificar nuevo viaje |
| POST | `/api/trips/<id>/action/` | Cambiar estado (start / complete / cancel) |
| POST | `/api/trips/<id>/events/` | Agregar evento a un viaje |
| GET/POST | `/api/fuel-price/` | Consultar / actualizar precio de combustible |

---

## Deploy en Render

1. Sube este repositorio a GitHub.
2. Crea un Web Service en Render conectado al repo.
3. Usa estos comandos:
   - Build Command:
     ```bash
     pip install -r requirements.txt && python manage.py collectstatic --noinput
     ```
   - Start Command:
     ```bash
     python manage.py migrate && gunicorn rutasia.wsgi:application --bind 0.0.0.0:$PORT --workers 3 --timeout 120
     ```
4. Configura las variables de entorno listadas en la seccion anterior.

---

## Licencia

Proyecto academico — Universidad Mesoamericana de Guatemala.
