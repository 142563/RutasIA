# LogistiRoute — Sistema de Optimización de Rutas

Sistema web de gestión y optimización de rutas logísticas para Guatemala. Permite planificar viajes entre departamentos usando algoritmos de camino más corto, gestionar pedidos, conductores y vehículos, y visualizar rutas en un mapa interactivo.

---

## Descripción del proyecto

LogistiRoute resuelve el problema de encontrar la ruta más corta entre cualquier par de departamentos de Guatemala, considerando las conexiones viales reales y sus distancias en kilómetros. El sistema:

- Calcula rutas óptimas usando el algoritmo de **Dijkstra** (grafo de distancias viales) o **A\*** (con heurística Haversine).
- Visualiza la ruta sobre un mapa vectorial con **MapLibre GL JS** y traza el trazado real por carreteras via **OpenRouteService**.
- Gestiona el ciclo de vida completo de un viaje: planificación → en progreso → completado / cancelado.
- Calcula costos estimados de combustible (GTQ/litro) y costo por kilómetro del vehículo.
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
| `FuelPrice` | Singleton con precios de combustible (regular, super, diesel) en GTQ/litro. |
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
