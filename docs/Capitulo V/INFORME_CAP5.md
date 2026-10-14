# Informe técnico para el Capítulo V: Diseño, desarrollo e implementación de la solución

Sistema **enruta** (repositorio `RutasIA`, producción en `https://enruta.world`, alojada en Render).
Fecha de elaboración: 2026-10-14. Rama `main`. **Actualizado el mismo día** tras alinear el código con la tesis (RUT-79): algoritmo genético como motor principal, OR-Tools como línea base, refuerzo exploratorio con TensorFlow y experimento de 3 escenarios × 10 repeticiones.

Regla de este informe: cada dato sale del código, de la configuración o de una ejecución real hecha el 2026-10-14. Cuando algo no existe, se dice "no existe en el código". No se incluye ningún valor de llaves ni contraseñas, solo nombres de variables.

---

## 1. Stack real con versiones

### 1.1 Lenguajes, frameworks y librerías

Fuente: `requirements.txt`, `requirements-dev.txt`, `runtime.txt`, `frontend/package.json`.

**Backend (Python 3.12.8, según `runtime.txt`)**

| Componente | Versión fijada | Uso |
|---|---|---|
| Django | 6.0.9 | Framework web, ORM, sesiones, CSRF, administración (`/admin/`) |
| psycopg[binary] | 3.2.12 | Conector PostgreSQL (Neon) |
| gunicorn | 22.0.0 | Servidor WSGI en Render |
| whitenoise | 6.7.0 | Archivos estáticos (incluido el build de React) desde Django |
| httpx | 0.27.0 | Cliente HTTP hacia Google Routes API y Resend |
| beautifulsoup4 | 4.12.3 | Está en `requirements.txt`. No se verificó en este informe en qué módulo se usa. |
| matplotlib | >=3.9 (solo `requirements-dev.txt`) | Gráficas de los experimentos (`logistics/routing/charts.py`); no se instala en Render |
| ortools | >=9.10 (solo `requirements-dev.txt`; instalada 9.15) | **Línea base** del algoritmo genético en el experimento de la tesis (`baseline_ortools.py`); nunca en el motor ni en la API |
| scipy, pandas | >=1.13, >=2.2 (solo `requirements-dev.txt`) | Estadística del experimento (Shapiro-Wilk, t pareada, Wilcoxon) y cuaderno de análisis |
| tensorflow | 2.19.1 (entorno aparte `experiments/colab/.venv-tf`, no versionado) | Cuaderno exploratorio de aprendizaje por refuerzo (Keras); compatible con Google Colab |

No hay otras librerías de Python en `requirements.txt` (lo que se instala en Render). Django exige Python 3.12 o superior (así lo declara `CLAUDE.md`; `runtime.txt` fija 3.12.8).

**Frontend (`frontend/package.json`; los números son rangos `^`, es decir, versión mínima)**

| Componente | Rango | Uso |
|---|---|---|
| React / react-dom | ^19.3.0 | Interfaz |
| react-router | ^8.4.0 | Rutas del cliente (`createBrowserRouter` en `frontend/src/App.tsx`) |
| @tanstack/react-query | ^5.104.0 | Consultas y caché de la API |
| TypeScript | ^7.0.2 | Lenguaje (`npm run build` ejecuta `tsc -b && vite build`) |
| Vite | ^8.3.1 | Empaquetador |
| Tailwind CSS + @tailwindcss/vite | ^4.3.3 | Estilos |
| radix-ui, class-variance-authority, clsx, tailwind-merge, lucide-react | ^1.6.7, ^0.7.1, ^2.1.1, ^3.7.0, ^1.48.0 | Componentes tipo shadcn |
| motion | ^14.1.0 | Animaciones |
| recharts | ^3.10.1 | Gráficas de Análisis |
| sonner | ^2.0.8 | Avisos emergentes |
| @fontsource-variable/geist, geist-mono | ^5.3.0 | Tipografía |
| @types/google.maps | ^3.66.4 (dev) | Tipos de la API de mapas |
| vitest | ^5.0.2 (dev) | Pruebas del frontend |

`package.json` solo da rangos. La versión exacta instalada se fija en el archivo de bloqueo que usa `npm ci` en Render (`render.yaml`); no se leyó en este informe.

### 1.2 Base de datos y ORM

- Producción: **PostgreSQL en Neon**, tomada de la variable `DATABASE_URL` (`rutasia/settings.py`, función `_database_config`: acepta solo esquemas `postgres://` o `postgresql://`, `CONN_MAX_AGE = 60`).
- Desarrollo local: si `DATABASE_URL` no existe o está vacía, usa **SQLite** (`db.sqlite3`, ignorado por Git).
- ORM: el **ORM de Django**. No hay SQL escrito a mano (lo afirma `docs/SEGURIDAD.md`; el ORM parametriza las consultas).
- Migraciones: `logistics/migrations/0001_initial.py` a `0019_genetic_optimizer.py` (19 archivos; la 0019 crea `OptimizerSettings` y agrega `Route.optimizer`).

### 1.3 Motor de optimización: es PROPIO

El motor está en `logistics/routing/` y usa solo la librería estándar de Python.

| Pieza | Archivo | Qué hace |
|---|---|---|
| Grafo en memoria | `logistics/routing/graph.py` (`RoadGraph`, `load_graph`, `build_graph_from_db`) | Carga nodos, aristas dirigidas y multiplicadores una sola vez; el costo de una arista es `t0 × m` |
| Dijkstra | `logistics/routing/dijkstra.py` (`dijkstra`, `dijkstra_all`) | `heapq`; punto a punto y uno-a-todos |
| A* | `logistics/routing/astar.py` (`astar`, `compute_v_max`, `heuristic`) | `heapq`; `h(n) = haversine(n, destino) / v_max`, con `v_max` derivado de los datos (máximo de recta/costo sobre todas las aristas) |
| Varias paradas | `logistics/routing/multistop.py` (`time_matrix`, `TimeDependentCost`, `plan_multistop`) | Matriz de tiempos con Dijkstra uno-a-todos, **orden con el algoritmo genético** y cada tramo final con A* |
| **Algoritmo genético (motor principal)** | `logistics/routing/genetic.py` (`GeneticParams`, `solve`, `ordered_crossover`, `mutate`, `fast_two_opt`) | Individuo = secuencia completa de entrega; aptitud = tiempo total estimado. Selección por torneo, cruce de orden (OX), mutación por intercambio o inversión, elitismo y búsqueda local 2-opt sobre élites y una fracción de hijos (variante memética). Semilla fija (reproducible). Se detiene por número de generaciones o por estancamiento |
| Línea base (solo experimentos) | `logistics/routing/baseline_ortools.py` | Google OR-Tools `RoutingModel` (PATH_CHEAPEST_ARC + GUIDED_LOCAL_SEARCH) sobre la misma matriz; importación perezosa, no está en `requirements.txt` |
| **Tráfico en vivo al planificar** | `logistics/application/live_planning.py` (`apply_live_traffic`) | Después de ordenar y trazar, Google Routes API (`computeRoutes` con tráfico) mide en vivo cada tramo elegido, pasando por los nodos de nuestro A*; los minutos y las llegadas de la ruta se recalculan con esas duraciones. Si Google falla, tarda o no hay llave, quedan los perfiles calibrados |
| Experimento de la tesis | `logistics/routing/thesis_experiment.py` y `manage.py run_thesis_experiment` | Convencional (proximidad sucesiva) contra optimizada (genético), 3 escenarios × 10 repeticiones, estadística (sección 7.6) |
| Instrumentación | `logistics/routing/instrument.py` (`SearchResult`) | Cada búsqueda devuelve nodos expandidos (`expanded`), inserciones (`pushed`), `elapsed_ms` y la ruta |
| Tráfico por franja | `logistics/routing/traffic.py` | 7 franjas horarias × 2 tipos de día (laboral, fin de semana); zona horaria `America/Guatemala` |
| Incidentes | `logistics/routing/incidents.py` | Penaliza una arista con un multiplicador ≥ 1 o la bloquea (costo infinito) |

**Cómo trabaja el genético dentro del sistema.**

1. Dijkstra uno-a-todos arma la matriz de minutos entre bodega y paradas con el tráfico de la franja de salida (y otra matriz por cada franja que la ruta llegue a cruzar).
2. La población inicial (80 individuos por defecto) incluye el orden de vecino más cercano, ese mismo orden mejorado con 2-opt, el orden de captura y un 20 % de individuos aleatorios pulidos con 2-opt; el resto es aleatorio. Así el resultado **nunca es peor** que la heurística anterior (vecino más cercano + 2-opt).
3. **Aptitud dependiente del tiempo** (`multistop.TimeDependentCost`): cada tramo cuesta lo que marca la franja en la que empieza, igual que cuando se traza con A*, sumando el tiempo de servicio de cada parada. Por eso el tiempo que estima el genético coincide exactamente con la suma de los tramos trazados (prueba `test_time_dependent_fitness_matches_the_traced_route`).
4. Parámetros por defecto (`GeneticParams`): población 80, máximo 400 generaciones, torneo de 3, probabilidad de cruce 0.9, de mutación 0.2, elitismo 2, parada tras 60 generaciones sin mejora, semilla 2026 y 2-opt sobre el 10 % de los hijos. **El administrador los ajusta** en `/admin/` (modelo `OptimizerSettings`, fila única); el servidor los acota a rangos seguros.
5. Con criterio de distancia (la ruta más corta), la aptitud son los km de la matriz, porque no dependen de la hora.
6. Igual que el resto del planificador, evita la terracería por defecto (penalización ×20 al elegir el camino).

**Tráfico en vivo (modelo híbrido, desde el 2026-10-14).** El orden de las paradas lo decide el genético con los multiplicadores calibrados por franja (Google, recalibrados cada domingo). Después, Google mide **en vivo** los tramos elegidos:

- Una consulta `computeRoutes` por tramo, con `TRAFFIC_AWARE_OPTIMAL` y la hora de salida de ese tramo (la de la solicitud si es futura; "ahora" si ya pasó). Los nodos de nuestro A* van como puntos intermedios (máximo 25 por consulta, límite de Google; si hay más se submuestrean parejo), así Google mide **nuestro** camino.
- Las consultas van en paralelo (8 a la vez), con caché de 5 minutos por tramo y franja de salida de 5 minutos, tope de `LIVE_TRAFFIC_TIMEOUT_S = 12` s y tope diario de `LIVE_TRAFFIC_DAILY_REQUESTS = 1 000` consultas.
- Todo o nada: si una consulta falla, se agota el tiempo, falta la llave o se llegó al tope, la ruta completa queda con los perfiles calibrados. La respuesta lo indica con `traffic_source` = `google_tiempo_real` o `perfil_calibrado`, la hora de la consulta y el motivo.
- Google nunca se llama dentro de Dijkstra ni de A*. Las pruebas nunca llaman a Google (`LIVE_TRAFFIC` se apaga al correr `manage.py test`).
- Se descartó usar la matriz completa en vivo como aptitud del genético por costo: con 20 planificaciones diarias serían unos US$961 al mes con 12 paradas y US$8 830 con 50 (tarifa oficial de Compute Route Matrix Pro).

**Bibliotecas.** El motor (Dijkstra, A* y el genético) usa solo la biblioteca estándar de Python; la prueba `test_engine_uses_only_standard_library` lo verifica. OR-Tools, SciPy, Pandas y TensorFlow solo aparecen en experimentos y cuadernos, nunca en el servidor de producción (`test_not_used_by_the_engine` verifica que ningún módulo del motor ni de la API importe OR-Tools). No se usan scikit-learn, networkx ni OSMnx.

### 1.4 APIs de Google realmente usadas

| API | Dónde se usa | Evidencia |
|---|---|---|
| **Routes API: `computeRouteMatrix`** (servidor) | `logistics/routing/google.py`, `RoutesClient.compute_route_matrix`; URL `https://routes.googleapis.com/distanceMatrix/v2:computeRouteMatrix`. La invocan los comandos por lotes `build_graph` y `calibrate_traffic` | Llave `GOOGLE_ROUTES_API_KEY`. Preferencias `TRAFFIC_UNAWARE` (t0) y `TRAFFIC_AWARE_OPTIMAL` (con tráfico) |
| **Routes API: `computeRoutes`** (servidor) | `RoutesClient.compute_route` (`https://routes.googleapis.com/directions/v2:computeRoutes`). Se usa para traer la geometría de los tramos (`logistics/routing/build.py`) y para la comprobación de tráfico en vivo (`logistics/application/live_traffic.py`, una consulta por tramo pendiente, con los nodos que eligió nuestro A* como puntos de paso) | Tope de 12 tramos y 25 intermedios por consulta; caché de 5 minutos |
| **Maps JavaScript API** (navegador) | `frontend/src/lib/googleMaps.ts` carga `https://maps.googleapis.com/maps/api/js` con la llave que entrega `/api/config/`; mapa base en `frontend/src/components/map/NetworkMap.tsx` | Llave `GOOGLE_MAPS_API_KEY` y `GOOGLE_MAPS_MAP_ID` |
| **Places API (New)** (navegador) | `frontend/src/lib/places.ts`: `google.maps.places.AutocompleteSuggestion` vía `importLibrary("places")`, restringido a Guatemala | Autocompletado de direcciones en `components/AddressAutocomplete.tsx` |
| **Geocoder** (navegador) | `frontend/src/lib/geocode.ts`: `importLibrary("geocoding")` y `new lib.Geocoder().geocode(...)`, para la dirección escrita a mano | Servicio del Maps JavaScript API |
| **Directions** (navegador) | `frontend/src/components/map/NetworkMap.tsx`, función `requestRoad`: `new google.maps.DirectionsService().route(...)`. Solo dibuja por dónde va la carretera entre los nodos que decidió nuestro algoritmo (`optimizeWaypoints: false`) | Si falla, dibuja líneas rectas |
| **TrafficLayer** (navegador) | `NetworkMap.tsx` línea 553: `new google.maps.TrafficLayer()`, capa visual de tráfico del mapa | Es visual; el motor no lee datos de ella (regla de `CLAUDE.md`) |

No existen en el código:

- La **Distance Matrix API clásica** (`maps.googleapis.com/maps/api/distancematrix`): `grep` de `distancematrix` no encuentra nada. Lo que se usa es `computeRouteMatrix` de la Routes API.
- La **Geocoding API REST** (`geocode/json`): no existe; el geocodificado se hace en el navegador con la clase `Geocoder` del Maps JavaScript API.

Regla de oro de diseño: **Google nunca se llama dentro del bucle de Dijkstra ni de A\*** (`logistics/routing/google.py`, encabezado). El motor trabaja con el grafo en memoria. Google se usa antes (para construir y calibrar el grafo, con caché en la tabla `RouteSample`), para dibujar, y después (para validar una ruta ya calculada, de forma informativa).

### 1.5 Correo: Resend

- `logistics/application/notifications/transport.py`: `httpx.post` a `https://api.resend.com/emails` (uno) y `https://api.resend.com/emails/batch` (lote), con la variable `RESEND_API_KEY`.
- Remitente: variable `NOTIFY_FROM` (valor en `render.yaml`: `enruta <entregas@enruta.world>`). Enlace base en correos: `SITE_URL` (`https://enruta.world`).
- Sin `RESEND_API_KEY` no se envía nada: se registra un log y una fila `NotificationLog` con estado `skipped` (`notifications/core.py`).
- Plantillas HTML y de texto en `logistics/templates/emails/` (13 correos, cada uno en `.html` y `.txt`, más parciales `_button`, `_details`, `_steps`, `base`).
- Los correos se programan con `transaction.on_commit` (función `later`) y dentro de `safely`, que captura cualquier excepción: un correo caído nunca rompe la operación.

### 1.6 Autenticación y seguridad de acceso

| Aspecto | Qué hay en el código |
|---|---|
| Sesión | Sesión de Django (cookie `HttpOnly`); `SESSION_COOKIE_AGE = 28800` (8 h); `SESSION_EXPIRE_AT_BROWSER_CLOSE = True`; cookies `Secure` si `DEBUG` es falso (`rutasia/settings.py`) |
| CSRF | `CsrfViewMiddleware` activo. El cliente pide la cookie en `GET /api/auth/csrf/` y envía el token en la cabecera `X-CSRFToken` (`logistics/presentation/app_views.py`). `CSRF_TRUSTED_ORIGINS` desde variable de entorno |
| Roles | `UserProfile.role` con `admin`, `dispatcher`, `driver` (`logistics/models.py`). Se verifican en el backend con `_require_role` (`logistics/presentation/serializers.py`) |
| Contraseña temporal | `logistics/application/fleet.py`: `generate_temp_password` (12 caracteres con `secrets`), vence en `TEMP_PASSWORD_HOURS = 72`. Se envía por correo (`notify_account_created`) y marca `UserProfile.must_change_password = True`. La SPA obliga a ir a `/cambiar-contrasena` (`RequireSession` en `App.tsx`); `POST /api/auth/password/` exige mínimo 10 caracteres y ejecuta `validate_password` |
| Validadores de contraseña | `AUTH_PASSWORD_VALIDATORS`: similitud con el usuario, longitud mínima, contraseñas comunes, solo numéricas |
| Límite de intentos | `logistics/application/login_limits.py`: ventana de 15 minutos, 5 fallos por cuenta (`ACCOUNT_LIMIT`) y 20 por IP (`IP_LIMIT`); responde 429. El contador vive en la tabla `LoginAttempt` (compartido entre los 3 workers), con identificadores en HMAC, no en claro. Aplica a `/api/auth/login/` y a `/accounts/login/` (`LimitedLoginView`) |
| Sesión vencida | `rutasia/middleware.py` (`ApiLoginRequiredMiddleware`) convierte la redirección 302 al login en un 401 JSON dentro de `/api/` |
| Login de demostración | `POST /api/auth/demo/`, solo si `DEMO_LOGIN` es verdadero (por defecto igual a `DEBUG`); solo despachador y conductor; nunca administrador |
| Política CSP | `rutasia/csp.py` emite `Content-Security-Policy-Report-Only` (modo reporte) y `POST /api/csp-report/` recibe los reportes |
| Diferencia con `docs/SEGURIDAD.md` | El documento indica HSTS, redirección HTTPS y `SECRET_KEY` privada obligatoria como "en revisión". En `rutasia/settings.py` de `main` **no existen** `SECURE_SSL_REDIRECT`, `SECURE_HSTS_*` ni la validación de la longitud de `SECRET_KEY` (`grep` sin resultados); sí existe `SECURE_PROXY_SSL_HEADER`. Además hay un valor de respaldo para `SECRET_KEY` cuando la variable no está definida |

### 1.7 Despliegue

Fuente: `render.yaml`, `Procfile`, `docs/EMPEZAR.md`.

| Servicio | Tipo | Configuración |
|---|---|---|
| `rutasia` | Web (Python) | Build: `cd frontend && npm ci && npm run build && cd .. && pip install -r requirements.txt && python manage.py collectstatic --noinput && python manage.py migrate --noinput`. Start: `gunicorn rutasia.wsgi:application --bind 0.0.0.0:$PORT --workers 3 --timeout 120` (igual que el `Procfile`) |
| `refresh-traffic` | Cron | Calendario `0 12 * * 0` (domingos 12:00 UTC = 06:00 de Guatemala). Build: `pip install -r requirements.txt`. Comando: `python manage.py refresh_traffic` (recalibra el tráfico con Google; solo vuelve a pedir muestras de más de 7 días) |

Variables de entorno declaradas en `render.yaml` (sin valores; `sync: false` significa que se capturan en el panel de Render):

- Servicio web: `DATABASE_URL`, `SECRET_KEY`, `GOOGLE_MAPS_API_KEY`, `GOOGLE_ROUTES_API_KEY`, `RESEND_API_KEY` (todas `sync: false`); `NOTIFY_FROM`, `SITE_URL`, `DEBUG` (con valor en el archivo).
- Cron: `DATABASE_URL`, `SECRET_KEY`, `GOOGLE_ROUTES_API_KEY` (`sync: false`) y `DEBUG`.
- Otras variables que lee `rutasia/settings.py` pero no están en `render.yaml`: `ALLOWED_HOSTS`, `CSRF_TRUSTED_ORIGINS`, `LOGIN_TRUSTED_PROXY_CIDRS`, `GOOGLE_MAPS_MAP_ID`, `DEMO_LOGIN`; y `DEMO_PASSWORD` (la exige el comando `seed_demo_users`).

Archivos estáticos: WhiteNoise (`whitenoise.middleware.WhiteNoiseMiddleware`) con un almacenamiento propio `rutasia.storage.StaticStorage`. El build de React (`frontend/dist/`) entra en `STATICFILES_DIRS`, y la vista `spa` (`logistics/presentation/app_views.py`) sirve `index.html` para cualquier ruta que no sea de API.

Dominio y correo (de `docs/EMPEZAR.md`, no verificable desde el código): dominio `enruta.world`, DNS administrado en **Spaceship**; registro A de la raíz hacia la dirección de Render, CNAME `www` hacia `rutasia.onrender.com`, registros DKIM/SPF de **Resend**. `docs/SEGURIDAD.md` (actualización del 2026-10-11) registra el dominio como verificado en Resend. HTTPS lo gestiona Render.

---

## 2. Arquitectura

### 2.1 Carpetas y responsabilidad

Patrón por capas (regla de `CLAUDE.md`): dominio, aplicación, presentación, más el motor.

| Carpeta | Responsabilidad |
|---|---|
| `rutasia/` | Proyecto Django: `settings.py`, `urls.py`, `middleware.py` (401 JSON en la API), `csp.py` (CSP en modo reporte), `storage.py` (estáticos), `wsgi.py` |
| `logistics/models.py` | Todos los modelos de datos (sección 4) |
| `logistics/domain/` | Reglas sin dependencia de la base: `exceptions.py` (`PlanningError`, `NotFoundError`), `regions.py` (8 regiones oficiales), `notifications.py` (matriz de qué correo recibe cada rol) |
| `logistics/application/` | Casos de uso: `planning.py` (planificar y crear ruta), `routing.py` (consultas del motor), `orders.py`, `assignment.py` (asignar y cancelar), `driver.py` (vista del conductor), `incidents.py` (incidentes y recálculo), `dispatch.py` (panel, monitoreo, reportes), `fleet.py` (bodegas, pilotos, camiones, usuarios), `live_traffic.py` (validación con Google), `login_limits.py`, `positions.py` (GPS), `tracking.py` (seguimiento público), `demo.py`, `notification_log.py`, y el paquete `notifications/` (`core`, `customer`, `staff`, `account`, `hooks`, `recipients`, `transport`) |
| `logistics/presentation/` | Vistas JSON delgadas: verifican método y rol, llaman al caso de uso y traducen errores. Archivos: `app_views`, `orders_views`, `dispatch_views`, `assignment_views`, `driver_views`, `fleet_views`, `incident_views`, `live_views`, `position_views`, `routing_views`, `password_views`, `tracking_views`, `notification_views`, `csp_views`, `login_views`, `serializers.py` (`_require_role`, `_ok`, `_error`, `_parse_json`) |
| `logistics/routing/` | Motor propio: grafo, Dijkstra, A*, varias paradas, tráfico por franja, incidentes, calibración, construcción del grafo (`build.py`), cliente de Google (`google.py`), datos semilla (`seed_data.py`), experimentos (`experiments.py`), datos sintéticos (`synthetic.py`), gráficas (`charts.py`) |
| `logistics/management/commands/` | Comandos: `preparar` (arranque en un paso), `seed_graph_nodes`, `build_graph`, `calibrate_traffic`, `refresh_traffic`, `run_experiments`, `check_google`, `seed_demo_users`, `seed_demo_data`, `clean_login_attempts`, `archive_legacy_orders` |
| `logistics/templates/emails/` | Plantillas de correo (HTML y texto) |
| `logistics/tests/` | 34 archivos de pruebas (sección 7) |
| `logistics/infrastructure/` | Solo contiene `__pycache__` (sin código fuente): la capa de infraestructura no tiene archivos |
| `frontend/src/pages/` | Pantallas (`Home`, `Login`, `orders`, `planner`, `routes`, `analysis`, `lab`, `traffic`, `reports`, `settings`, `driver`, `account`, `tracking`, `monitoring` con componentes de la pantalla Hoy) |
| `frontend/src/components/` | Componentes reutilizables: `map/NetworkMap.tsx`, `layout/AppShell.tsx`, `ui/` (estilo shadcn), `AddressAutocomplete`, `NodeSearch`, `DataSourceNote`, `NotificationsSent` |
| `frontend/src/lib/` | Acceso a la API (`api.ts`), hooks de datos por tema (`planning.ts`, `dispatch.ts`, `incidents.ts`, `fleet.ts`, etc.), integración con Google (`googleMaps.ts`, `places.ts`, `geocode.ts`, `roads.ts`, `polyline.ts`), sesión (`auth.tsx`, `sessionCache.ts`) y lógica pura con sus pruebas (`*.test.ts`) |
| `docs/` | Plan, seguridad, guías |
| `experiments/output/` | Salida por defecto de `run_experiments` (CSV y PNG); la carpeta está en `.gitignore` |

### 2.2 Endpoints REST

Fuente: `logistics/urls.py`, `rutasia/urls.py` y la lectura de cada vista. "Sesión" significa `@login_required` (sin sesión, el middleware responde 401 JSON). "Despacho" = `admin` o `dispatcher`.

| Método | Ruta | Vista | Rol requerido | Propósito |
|---|---|---|---|---|
| GET | `/api/auth/csrf/` | `app_views.api_csrf` | Ninguno | Entrega la cookie CSRF |
| POST | `/api/auth/login/` | `app_views.api_login` | Ninguno (con límite de intentos, 429) | Inicia sesión; rechaza con 403 una contraseña temporal vencida |
| POST | `/api/auth/logout/` | `app_views.api_logout` | Ninguno | Cierra sesión |
| GET | `/api/auth/session/` | `app_views.api_session` | Ninguno (401 si no hay sesión) | Usuario actual y su rol |
| POST | `/api/auth/demo/` | `app_views.api_demo_login` | Ninguno; solo con `DEMO_LOGIN` | Entrada de un clic como despachador o conductor |
| GET | `/api/config/` | `app_views.api_config` | Ninguno (público) | Llave del navegador de Google, `map_id` y bandera `demo_login` |
| POST | `/api/auth/password/` | `password_views.api_password_change` | Sesión (cualquier rol) | Cambia la contraseña (obligatorio con la temporal) |
| GET | `/api/public/tracking/<token>/` | `tracking_views.api_public_tracking` | **Ninguno** (público, con token) | Seguimiento del pedido para el cliente final; datos mínimos y `Cache-Control: no-store` |
| POST | `/api/csp-report/` | `csp_views.api_csp_report` | Ninguno (`csrf_exempt`) | Recibe reportes de la política CSP |
| GET, POST | `/api/v2/orders/` | `orders_views.api_v2_orders` | Despacho | Lista pedidos / crea un pedido |
| GET | `/api/v2/depots/` | `orders_views.api_v2_depots` | Despacho | Lista bodegas |
| POST | `/api/v2/routes/plan/` | `orders_views.api_v2_routes_plan` | Despacho | Calcula, sin guardar, la ruta más rápida y la más corta, y la comparación por hora de salida |
| GET, POST | `/api/v2/routes/` | `orders_views.api_v2_routes` | Despacho | Lista las 50 rutas más recientes / confirma y guarda una ruta |
| GET | `/api/v2/routes/<id>/` | `dispatch_views.api_v2_route_detail` | Despacho | Detalle de una ruta |
| GET | `/api/v2/routes/<id>/positions/` | `position_views.api_route_positions` | Despacho | Traza GPS de una ruta |
| POST | `/api/v2/routes/<id>/live-check/` | `live_views.api_route_live_check` | Sesión; el conductor solo en sus rutas (404 en las ajenas) | Compara la llegada estimada con Google ahora mismo (solo informa) |
| GET | `/api/v2/assignment/options/` | `assignment_views.api_assignment_options` | Despacho | Conductores y camiones disponibles/sugeridos |
| POST | `/api/v2/routes/<id>/assign/` | `assignment_views.api_route_assign` | Despacho | Asigna o reasigna conductor y camión |
| POST | `/api/v2/routes/<id>/cancel/` | `assignment_views.api_route_cancel` | Despacho | Cancela una ruta y libera sus pedidos |
| GET | `/api/v2/dashboard/` | `dispatch_views.api_v2_dashboard` | Despacho | Cifras de la pantalla Hoy |
| GET | `/api/v2/monitoring/` | `dispatch_views.api_v2_monitoring` | Despacho | Monitoreo en vivo de rutas e incidentes |
| GET | `/api/v2/reports/` | `dispatch_views.api_v2_reports` | Despacho | Resumen de reportes y de los CSV de experimentos |
| GET | `/api/v2/notifications/` | `notification_views.api_notifications` | Despacho | Bitácora "Avisos enviados" |
| GET, POST | `/api/v2/fleet/<kind>/` | `fleet_views.api_fleet_collection` | `kind` = depots, drivers, vehicles: GET para despacho, POST solo admin. `kind` = users: solo admin | Lista / crea bodegas, pilotos, camiones y usuarios |
| GET, PATCH, DELETE | `/api/v2/fleet/<kind>/<id>/` | `fleet_views.api_fleet_item` | Igual que arriba (GET de depots/drivers/vehicles para despacho; el resto, admin) | Consulta, edita o desactiva (DELETE desactiva) un elemento |
| POST | `/api/v2/fleet/users/<id>/resend-access/` | `fleet_views.api_fleet_user_resend_access` | Admin | Genera otra contraseña temporal y la envía por correo |
| GET | `/api/driver/today/` | `driver_views.api_driver_today` | Conductor | Rutas del día del conductor |
| GET | `/api/driver/routes/<id>/map/` | `driver_views.api_driver_route_map` | Conductor (solo su ruta) | Nodos y geometría de su ruta para navegar |
| POST | `/api/driver/routes/<id>/start/` | `driver_views.api_driver_route_start` | Conductor (solo su ruta) | Inicia la ruta |
| POST | `/api/driver/stops/<id>/` | `driver_views.api_driver_stop_update` | Conductor (solo sus paradas) | Marca la parada como entregada o no entregada (con motivo) |
| POST | `/api/driver/position/` | `position_views.api_driver_position` | Conductor | Registra la posición GPS (límite de frecuencia, 429) |
| GET | `/api/routing/nodes/` | `routing_views.api_routing_nodes` | Despacho | Nodos y tramos del grafo |
| GET | `/api/routing/geometry/` | `routing_views.api_routing_geometry` | Despacho | Geometría guardada de pares dirigidos |
| POST | `/api/routing/route/` | `routing_views.api_routing_route` | Despacho | Ruta punto a punto (Dijkstra o A*) |
| POST | `/api/routing/compare/` | `routing_views.api_routing_compare` | Despacho | Dijkstra contra A*, y más rápida contra más corta |
| POST | `/api/routing/explore/` | `routing_views.api_routing_explore` | Despacho | Orden de expansión de ambos algoritmos (Laboratorio) |
| GET | `/api/routing/best-departure/` | `routing_views.api_routing_best_departure` | Despacho | Tiempo del mismo viaje saliendo en cada franja del día |
| POST | `/api/routes/optimize/` | `routing_views.api_routes_optimize` | Despacho | Varias paradas (hasta 50) con el motor |
| GET | `/api/traffic/profile/` | `routing_views.api_traffic_profile` | Despacho | Multiplicadores de tráfico por franja y tipo de día |
| GET, POST | `/api/traffic/incidents/` | `incident_views.api_incidents` | Sesión con cualquiera de los 3 roles | GET: incidentes vigentes y propuestas pendientes (el conductor solo ve las de sus rutas). POST: reporta un incidente y dispara el recálculo |
| POST | `/api/traffic/incidents/<id>/resolve/` | `incident_views.api_incident_resolve` | Despacho, o quien reportó el incidente | Marca el incidente como resuelto |
| POST | `/api/reroutes/<id>/decision/` | `incident_views.api_reroute_decision` | Conductor dueño de la ruta, o despacho | Acepta (`accept`) o mantiene (`keep`) la ruta alternativa |

Rutas de `rutasia/urls.py`:

| Ruta | Vista | Propósito |
|---|---|---|
| `/admin/` | `admin.site.urls` | Administración de Django |
| `/accounts/login/` | `LimitedLoginView` | Login clásico con límite de intentos |
| `/accounts/...` | `django.contrib.auth.urls` | Vistas de autenticación estándar de Django |
| `""` y cualquier otra ruta que no empiece por `api/`, `admin/`, `accounts/`, `static/` | `app_views.spa` | Entrega el `index.html` de React; el router del cliente resuelve la pantalla |

Los endpoints antiguos (`/api/drivers/`, `/api/orders/`, `/api/trips/*`) y la interfaz `/clasico/` fueron retirados (RUT-40, según `CLAUDE.md`).

---

## 3. Roles reales

`UserProfile.Role` (`logistics/models.py`): `admin` ("Administrador"), `dispatcher` ("Despachador"), `driver` ("Conductor"). Si un usuario no tiene perfil, `role_for` (`serializers.py`) lo trata como `admin` solo si es superusuario; en otro caso, como `driver` (el de menos permisos).

### 3.1 Qué puede hacer cada rol (verificado en las vistas)

| Capacidad | Administrador | Despachador | Conductor |
|---|---|---|---|
| Crear y listar pedidos (`/api/v2/orders/`) | Sí | Sí | No (403) |
| Planificar y confirmar rutas (`/api/v2/routes/plan/`, `/api/v2/routes/`) | Sí | Sí | No |
| Asignar, reasignar y cancelar rutas | Sí | Sí | No |
| Ver detalle de rutas, panel Hoy, monitoreo, reportes, traza GPS | Sí | Sí | No |
| Usar el motor directamente (`/api/routing/*`, `/api/routes/optimize/`, `/api/traffic/profile/`) | Sí | Sí | No (403; prueba `test_routing_roles.py`) |
| Ver bodegas, pilotos y camiones (GET de `/api/v2/fleet/`) | Sí | Sí | No |
| Crear, editar o desactivar bodegas, pilotos, camiones | Sí | No | No |
| Gestionar usuarios y reenviar contraseña temporal | Sí | No | No |
| Ver la bitácora de correos (`/api/v2/notifications/`) | Sí | Sí | No |
| Ver sus rutas del día, iniciar su ruta, marcar entregas, enviar GPS, ver el mapa de su ruta | No (403) | No (403) | Sí, solo lo propio |
| Reportar un incidente | Sí | Sí | Sí |
| Resolver un incidente | Sí | Sí | Solo uno que él reportó |
| Aceptar o mantener una ruta alternativa | Sí | Sí | Solo en sus rutas |
| Comprobar tráfico en vivo de una ruta (`live-check`) | Sí | Sí | Solo en sus rutas |
| Cambiar su contraseña | Sí | Sí | Sí |

En la interfaz (`frontend/src/App.tsx`): las pantallas de gestión exigen `admin` o `dispatcher` y las del conductor exigen `driver`. La sección Configuración está además limitada a `admin` (menú `adminOnly` en `AppShell.tsx` y pantalla `SettingsPage.tsx`). El backend repite la verificación, de modo que ocultar un menú no es la única barrera.

### 3.2 Comparación con los roles de la tesis

| Rol o actor de la tesis | Equivalente en el sistema | Coincidencia o diferencia |
|---|---|---|
| Coordinador de rutas | `dispatcher` (Despachador) | Coincide en lo esencial: captura pedidos, planifica, asigna y aprueba recálculos. Diferencia: el sistema también deja al administrador hacer todo lo del despachador |
| Mensajero | `driver` (Conductor) | Coincide: ve solo su ruta, navega, marca entregas, reporta incidentes y recibe rutas alternativas. Se le asocia un registro `Driver` con cuenta de usuario |
| Administrador del sistema | `admin` (Administrador) | Coincide, y suma la gestión de bodegas, pilotos, camiones y usuarios (Configuración), que ningún otro rol tiene |
| API de Google Maps (sistema externo) | Google Routes API (servidor) y Google Maps JavaScript API, Places, Geocoder, Directions (navegador) | Coincide como sistema externo. Precisión: se usan dos llaves distintas y varias APIs (sección 1.4); el motor no depende de Google en el momento de calcular |
| (no está en la lista de la tesis) Cliente final | **No tiene cuenta**. Es el destinatario del pedido (`Order.recipient`, `recipient_email`) | Recibe correos de pedido recibido, ruta programada, ruta iniciada, entregado y entrega fallida (conjunto `CUSTOMER_EVENTS` en `domain/notifications.py`) y puede abrir `/seguimiento/<token>` sin iniciar sesión. Es un actor real del sistema que la tesis no lista |
| (no está en la lista de la tesis) Resend | Servicio externo de correo transaccional | Segundo sistema externo, además de Google |
| (no está en la lista de la tesis) Neon, Render | Infraestructura (base de datos y alojamiento) | No son actores funcionales, pero participan del despliegue |

---

## 4. Modelo de datos

Fuente: `logistics/models.py` y `django.contrib.auth`. Todos los modelos usan clave primaria entera autoincremental (`DEFAULT_AUTO_FIELD = BigAutoField`) salvo que se indique otra cosa. `TimestampedModel` (abstracto) agrega `created_at` (`DateTimeField`, `auto_now_add`) y `updated_at` (`DateTimeField`, `auto_now`); se marca "TS" donde se hereda.

### 4.1 Usuario de Django (`django.contrib.auth.models.User`)

Tabla estándar `auth_user`: `id` (PK), `username` (único), `password` (hash), `email`, `first_name`, `last_name`, `is_staff`, `is_active`, `is_superuser`, `last_login` (nulo), `date_joined`. El proyecto lo extiende con `UserProfile` (uno a uno) y no lo reemplaza.

### 4.2 Modelos activos

**UserProfile**

| Campo | Tipo | Nulo | Notas |
|---|---|---|---|
| `user` | `OneToOneField(User, CASCADE)`, `related_name="profile"` | No | Único por ser uno a uno |
| `role` | `CharField(20)`, choices `admin`/`dispatcher`/`driver` | No | Por defecto `dispatcher` |
| `must_change_password` | `BooleanField` | No | Por defecto falso |
| `temp_password_expires_at` | `DateTimeField` | Sí | |

**Driver** (TS)

| Campo | Tipo | Nulo | Notas |
|---|---|---|---|
| `user` | `OneToOneField(User, SET_NULL)`, `related_name="driver"` | Sí | Cuenta con la que entra a su vista móvil |
| `name` | `CharField(120)` | No | |
| `phone` | `CharField(20)` | No (puede ser vacío) | |
| `license_number` | `CharField(30)` | No | Único |
| `last_position_at` | `DateTimeField` | Sí | |
| `is_active` | `BooleanField` | No | Por defecto verdadero |

**Vehicle** (TS)

| Campo | Tipo | Nulo | Notas |
|---|---|---|---|
| `plate` | `CharField(16)` | No | Único |
| `model` | `CharField(100)` | No | |
| `capacity_kg` | `DecimalField(8,2)` | No | |
| `fuel_efficiency_km_l` | `DecimalField(8,2)` | No | |
| `cost_per_km` | `DecimalField(8,2)` | No | |
| `is_active` | `BooleanField` | No | Por defecto verdadero |
| `current_department` | `ForeignKey(Department, SET_NULL)`, `related_name="vehicles"` | Sí | Campo heredado (usa el modelo heredado `Department`) |
| `driver` | `ForeignKey(Driver, SET_NULL)`, `related_name="vehicles"` | Sí | Conductor habitual |

**Order** (TS)

| Campo | Tipo | Nulo | Notas |
|---|---|---|---|
| `code` | `CharField(24)` | No | Único; se genera `PED-AAAAMMDD-NNNN` |
| `origin`, `destination` | `ForeignKey(Department, PROTECT)` | Sí | Heredados de la interfaz clásica; opcionales |
| `recipient` | `CharField(120)` | No (vacío permitido) | |
| `phone` | `CharField(30)` | No (vacío permitido) | |
| `recipient_email` | `EmailField` | No (vacío permitido) | Correo del cliente para avisos |
| `tracking_token` | `CharField(32)` | No | Único; `secrets.token_urlsafe(16)` (22 caracteres); no editable |
| `address`, `reference`, `place_id` | `CharField(255)` | No (vacío permitido) | |
| `latitude`, `longitude` | `FloatField` | Sí | |
| `node` | `ForeignKey(Node, SET_NULL)`, `related_name="orders"` | Sí | Nodo del grafo más cercano |
| `is_demo` | `BooleanField` | No | |
| `weight_kg` | `DecimalField(8,2)` | No | |
| `package_count` | `PositiveIntegerField` | No | Por defecto 1 |
| `priority` | `CharField(10)`, choices `low`/`normal`/`high` | No | Por defecto `normal` |
| `status` | `CharField(16)`, choices `pending`, `assigned`, `in_transit`, `delivered`, `failed`, `canceled` | No | Por defecto `pending` |
| `requested_for` | `DateTimeField` | No | Por defecto la hora actual |

**Depot** (TS): `name` (`CharField(120)`, único), `address` (`CharField(255)`, vacío permitido), `latitude`, `longitude` (`FloatField`), `node` (`ForeignKey(Node, SET_NULL)`, nulo, `related_name="depots"`), `is_active`.

**Node**: `code` (`SlugField(40)`, único), `name` (`CharField(120)`), `kind` (`CharField(10)`: `cabecera`, `municipio`, `cruce`), `department` (`CharField(2)`, 22 departamentos de Guatemala en `GuatemalaDepartment`), `latitude`, `longitude` (`FloatField`), `is_active`. Restricción `node_inside_guatemala` (coordenadas dentro del recuadro lat 13.5 a 18.0, lon -92.5 a -88.0).

**Edge** (TS): arista **dirigida**.

| Campo | Tipo | Nulo | Notas |
|---|---|---|---|
| `origin`, `destination` | `ForeignKey(Node, CASCADE)`, `related_name` `edges_out` / `edges_in` | No | |
| `distance_km` | `FloatField` | No | Debe ser mayor que 0 |
| `duration_free_min` | `FloatField` | No | t0, minutos sin tráfico; mayor que 0 |
| `polyline` | `TextField` | No (vacío permitido) | Geometría codificada |
| `road` | `CharField(20)` | No (vacío permitido) | Carretera principal, p. ej. CA-1 |
| `source` | `CharField(10)`: `google`, `manual`, `estimate` | No | Por defecto `google` |
| `road_class` | `CharField(10)`: `primary`, `secondary`, `unpaved` | No | Por defecto `secondary` |
| `verified_at` | `DateTimeField` | Sí | |
| `is_active` | `BooleanField` | No | |

Restricciones: única `(origin, destination)`; origen distinto de destino; distancia y duración positivas.

**TrafficProfile**: `edge` (`ForeignKey(Edge, CASCADE)`, `related_name="traffic_profiles"`), `band` (`CharField(12)`: `dawn`, `peak_am`, `mid_morning`, `midday`, `afternoon`, `peak_pm`, `night`), `day_type` (`CharField(8)`: `weekday`, `weekend`), `multiplier` (`FloatField`), `calibrated_at` (`DateTimeField`, por defecto ahora), `source` (`CharField(40)`, por defecto `google_routes`). Restricciones: única `(edge, band, day_type)` y `multiplier >= 1.0` a nivel de base de datos. 260 aristas × 14 perfiles = 3 640 filas (cifra que imprime `calibrate_traffic`).

**RouteSample** (caché y bitácora de Google): `origin`, `destination` (`ForeignKey(Node, CASCADE)`, `related_name` `samples_out` / `samples_in`), `band`, `day_type` (vacíos si la consulta fue sin tráfico), `departure_time` (nulo), `routing_preference` (`CharField(30)`), `status` (`CharField(40)`, vacío = correcto), `duration_s`, `static_duration_s`, `distance_m` (`FloatField`, nulos), `polyline` (`TextField`), `fetched_at`. Única `(origin, destination, band, day_type)`.

**Route** (TS)

| Campo | Tipo | Nulo | Notas |
|---|---|---|---|
| `code` | `CharField(24)` | No | Único; `RUT-AAAAMMDD-NNNN` |
| `depot` | `ForeignKey(Depot, PROTECT)`, `related_name="routes"` | No | |
| `driver` | `ForeignKey(Driver, SET_NULL)`, `related_name="routes"` | Sí | |
| `vehicle` | `ForeignKey(Vehicle, SET_NULL)`, `related_name="routes"` | Sí | |
| `created_by` | `ForeignKey(User, SET_NULL)`, `related_name="+"` | Sí | Despachador que la creó |
| `departure_at` | `DateTimeField` | No | |
| `criterion` | `CharField(10)`: `time` (más rápida), `distance` (más corta) | No | Por defecto `time` |
| `optimizer` | `CharField(16)`: `genetic`, `nn2opt` o `fixed` | Sí (vacío en rutas anteriores) | Algoritmo que ordenó las paradas; por defecto `genetic` (RUT-79) |
| `algorithm` | `CharField(16)` | No | Por defecto `astar` |
| `return_to_depot` | `BooleanField` | No | Por defecto verdadero |
| `service_min` | `FloatField` | No | Por defecto 10 |
| `driving_minutes` | `FloatField` | No | Minutos de manejo con el tráfico de cada tramo |
| `total_km` | `FloatField` | No | |
| `shortest_minutes` | `FloatField` | Sí | Minutos de la más corta con el mismo tráfico (base del ahorro) |
| `expanded_nodes` | `PositiveIntegerField` | No | Nodos expandidos (matriz con Dijkstra + tramos con A*) |
| `finish_at` | `DateTimeField` | No | |
| `legs` | `JSONField` | No | Tramos: nodos, minutos, `free_minutes`, km, franja, `expanded` |
| `data_source` | `CharField(80)` | No (vacío permitido) | Procedencia de los datos |
| `status` | `CharField(16)`: `planned`, `in_progress`, `completed`, `canceled` | No | Por defecto `planned` |
| `started_at`, `completed_at` | `DateTimeField` | Sí | |

**RouteStop**: `route` (`ForeignKey(Route, CASCADE)`, `related_name="stops"`), `order` (`ForeignKey(Order, PROTECT)`, `related_name="route_stops"`), `sequence` (`PositiveIntegerField`), `eta` (`DateTimeField`), `status` (`pending`, `delivered`, `failed`; por defecto `pending`), `reason` (`CharField(120)`, vacío permitido), `delivered_at` (nulo). Únicas `(route, sequence)` y `(route, order)`.

**VehiclePosition**: `route` (`ForeignKey(Route, CASCADE)`, `related_name="positions"`), `driver` (`ForeignKey(Driver, CASCADE)`, `related_name="positions"`), `lat`, `lng` (`FloatField`), `speed_kmh`, `heading`, `accuracy_m` (`FloatField`, nulos), `recorded_at` (por defecto ahora), `source` (`phone`/`tracker`). Índice `(route, recorded_at)` y restricciones de rango (latitud, longitud, velocidad 0 a 300, rumbo 0 a menos de 360, precisión 0 a 100 000).

**Incident** (TS): `kind` (`traffic`, `accident`, `landslide`, `closure`), `edges` (`ManyToManyField(Edge)`, `related_name="incidents"`), `blocked` (`BooleanField`), `multiplier` (`FloatField`, por defecto 1.0; restricción `>= 1.0`), `starts_at`, `ends_at` (nulo), `note` (`CharField(255)`), `reported_by` (`ForeignKey(User, SET_NULL)`, nulo), `route` (`ForeignKey(Route, SET_NULL)`, nulo, `related_name="incidents"`), `resolved_at` (nulo).

**RerouteProposal** (TS): `route` (`ForeignKey(Route, CASCADE)`, `related_name="reroutes"`), `incident` (`ForeignKey(Incident, SET_NULL)`, nulo, `related_name="reroutes"`), `current_minutes`, `proposed_minutes` (`FloatField`), `proposed_legs` (`JSONField`), `summary` (`CharField(200)`), `status` (`pending`, `accepted`, `kept`, `expired`), `decided_by` (`ForeignKey(User, SET_NULL)`, nulo), `decided_at` (nulo).

**OptimizerSettings** (fila única, `pk = 1`; RUT-79): parámetros del algoritmo genético que ajusta el administrador en `/admin/`: `population` (80), `generations` (400), `tournament` (3), `crossover_rate` (0.9), `mutation_rate` (0.2), `elitism` (2), `stall_generations` (60), `seed` (2026, nulo = aleatoria), `local_search` (sí), `local_search_rate` (0.1), `updated_at`. Sin fila se usan esos valores por defecto; el servidor los acota a rangos seguros. No tiene relaciones.

**NotificationLog**: `event` (`CharField(32)`), `audience` (`customer`/`staff`), `recipient` (`EmailField(254)`), `subject` (`CharField(200)`), `user` (`ForeignKey(User, SET_NULL)`, nulo), `order` (`ForeignKey(Order, SET_NULL)`, nulo, `related_name="notifications"`), `route` (`ForeignKey(Route, SET_NULL)`, nulo, `related_name="notifications"`), `status` (`sent`/`failed`/`skipped`), `provider_id` (`CharField(80)`, id del correo en Resend), `error` (`CharField(300)`), `dedupe_key` (`CharField(160)`, con índice), `created_at`. No guarda el cuerpo del correo.

**LoginAttempt**: `key` (`CharField(80)`, único; HMAC del identificador), `failures` (`JSONField`, lista de marcas de tiempo), `blocked_until` (nulo), `touched_at` (con índice).

### 4.3 Modelos heredados que se conservan sin uso

`CLAUDE.md` los declara conservados como datos históricos, sin migración que los borre, y "ningún código nuevo los usa". En el código se verificó que `Order.origin`/`destination` y `Vehicle.current_department` todavía apuntan a `Department`.

| Modelo | Campos | Observación |
|---|---|---|
| `Department` | `code` (único, 8), `name` (único, 80), `latitude`, `longitude` (`DecimalField(9,6)`, nulos) | Reemplazado por `Node` (grafo nacional) |
| `RouteConnection` (TS) | `origin`, `destination` (`ForeignKey(Department, CASCADE)`), `distance_km` (`DecimalField(8,2)`), `is_bidirectional` | Reemplazado por `Edge`; única `(origin, destination)` |
| `Trip` (TS) | `code` (único), `vehicle` (`PROTECT`), `driver` (`SET_NULL`), `origin`/`destination` (`Department`, `PROTECT`), `orders` (`ManyToMany` a `Order` vía `TripOrder`), `route_nodes` (`JSONField`), distancia, combustible y costos (`DecimalField`), `status`, `started_at`, `completed_at` | Reemplazado por `Route` y `RouteStop` |
| `TripOrder` | `trip` y `order` (`ForeignKey`, `CASCADE`); única `(trip, order)` | Tabla intermedia de `Trip` |
| `TripEvent` (TS) | `trip` (`CASCADE`), `note` (`TextField`) | Bitácora de `Trip` |
| `FuelPrice` (TS) | `regular_gtq_gal`, `super_gtq_gal`, `diesel_gtq_gal` (`DecimalField(6,2)`), `source` (`CharField(120)`) | Registro único (`current()` usa `pk=1`); sin uso en el motor nuevo |

### 4.4 Relaciones y cardinalidad

| Relación | Cardinalidad |
|---|---|
| `User` — `UserProfile` | 1 a 1 |
| `User` — `Driver` | 1 a 0..1 (el conductor puede no tener cuenta) |
| `Driver` — `Vehicle` | 1 a N (un conductor habitual puede tener varios camiones; un camión tiene 0..1 conductor habitual) |
| `Depot` — `Route` | 1 a N |
| `Driver` — `Route`, `Vehicle` — `Route` | 1 a N cada una (una ruta tiene 0..1 conductor y 0..1 camión) |
| `User` — `Route` (`created_by`) | 1 a N |
| `Route` — `RouteStop` | 1 a N |
| `Order` — `RouteStop` | 1 a N en el modelo; la restricción `(route, order)` impide repetir un pedido dentro de la misma ruta |
| `Route` — `Order` | N a M a través de `RouteStop` |
| `Node` — `Edge` | 1 a N como origen y 1 a N como destino (grafo dirigido) |
| `Edge` — `TrafficProfile` | 1 a N (hasta 14 por arista) |
| `Node` — `Order`, `Node` — `Depot` | 1 a N (cada pedido y bodega se asocia al nodo más cercano) |
| `Incident` — `Edge` | N a M |
| `Route` — `Incident` | 1 a N (incidente reportado desde una ruta) |
| `Route` — `RerouteProposal`, `Incident` — `RerouteProposal` | 1 a N cada una |
| `Route` — `VehiclePosition`, `Driver` — `VehiclePosition` | 1 a N cada una |
| `Order` — `NotificationLog`, `Route` — `NotificationLog`, `User` — `NotificationLog` | 1 a N cada una (todas opcionales, `SET_NULL`) |

---

## 5. Flujos principales

### 5.1 Generar una ruta optimizada

1. **Pantalla.** `frontend/src/pages/planner/PlannerPage.tsx` arma una solicitud (bodega, pedidos, hora de salida, tiempo de servicio, regresar a la bodega, evitar terracería). El hook `usePlan` de `frontend/src/lib/planning.ts` hace `POST /api/v2/routes/plan/` (consulta, no guarda).
2. **Vista.** `orders_views.api_v2_routes_plan` verifica el rol (admin o despachador) y llama a `planning.plan_route` en `logistics/application/planning.py`.
3. **Validación.** `planning._parse_request` carga el grafo con `routing.get_graph()` (grafo en memoria, `routing.py`), exige bodega activa, 1 a `MAX_STOPS = 50` pedidos pendientes, tiempo de servicio de 0 a 120 min, y convierte la hora de salida (`parse_departure`).
4. **Dos variantes con el mismo tráfico.**
   - `planning._shortest` llama a `_plan(..., criterion="distance")`: ruta más corta en km.
   - `planning._fastest` evalúa tres candidatos y elige el de menos minutos: orden optimizado por tiempo, orden de la más corta recorrido por tiempo, y la más corta. Por construcción la más rápida nunca tarda más que la más corta.
5. **Motor de varias paradas.** `planning._plan` llama a `routing.multistop.plan_multistop` (`logistics/routing/multistop.py`):
   1. Obtiene la franja y el tipo de día de la hora de salida (`traffic.profile_for`) y los pesos `graph.search_weights(criterion, band, day_type, avoid_unpaved)`, es decir, `t0 × m` por arista (o km). La terracería se multiplica por `UNPAVED_PENALTY = 20` si se pide evitarla (factor mayor o igual a 1).
   2. `time_matrix` calcula la matriz de tiempos entre bodega y paradas con Dijkstra uno-a-todos (`dijkstra.py`).
   3. El **algoritmo genético** (`genetic.solve`) ordena las paradas, sembrado con vecino más cercano + 2-opt y con aptitud dependiente del tiempo (sección 1.3). El plan registra `optimizer = "genetic"`, las generaciones usadas y los milisegundos.
   4. Para cada tramo se recorre el reloj: se toma la franja del instante de salida de ese tramo, se corre **A\*** (`astar.py`) con los pesos de esa franja, se acumulan minutos y km, y se suma el tiempo de servicio en cada parada para obtener las llegadas estimadas (ETA).
   - **Tráfico en vivo (al terminar el motor).** `live_planning.apply_live_traffic` manda a Google, en paralelo, los tramos de la ruta más rápida y de la más corta (los que comparten tramo se consultan una vez) y reemplaza sus minutos y llegadas con el tráfico del momento. Si con el tráfico en vivo la más corta resulta más rápida, pasa a ser la más rápida (`_faster`). Las opciones de hora de salida (7 franjas) siguen con los perfiles calibrados, para no multiplicar las consultas.
6. **Respuesta de planificación.** `_variant_payload` devuelve para cada variante: orden de paradas con ETA, tramos (`nodes`, `roads`, `minutes`, `free_minutes`, `km`, `band`, `expanded`), minutos de manejo, minutos extra por tráfico, km y nodos expandidos. `plan_route` añade `minutes_saved` (minutos de la más corta menos los de la más rápida), `departure_options` (`_departure_options`: la más rápida saliendo a la hora representativa de cada una de las 7 franjas) y `data_source`.
7. **Confirmar.** El hook `useCreateRoute` hace `POST /api/v2/routes/` con el criterio elegido y, si aplica, conductor y camión. `orders_views.api_v2_routes` llama a `planning.create_route`, decorada con `@transaction.atomic`:
   - Bloquea los pedidos con `select_for_update` (evita asignarlos dos veces).
   - **Recalcula en el servidor** (no confía en el cliente): `_shortest` y `_fastest`/`_shortest` según el criterio.
   - `assignment.validate_for_new_route` comprueba que conductor y camión estén activos y que el peso quepa en la capacidad; `assignment.ensure_available` verifica que no haya choque de horario con otras rutas.
   - Vuelve a aplicar el tráfico en vivo (sale de la caché de 5 minutos si se confirma poco después de planificar).
   - Crea `Route` (con `driving_minutes`, `total_km`, `shortest_minutes`, `expanded_nodes`, `legs`, `data_source`, `traffic_source` y `traffic_queried_at`), crea las `RouteStop` con `bulk_create` y pasa los pedidos a `assigned`.
8. **Avisos por correo.** Al final, `later(on_route_created, route.id)` (`notifications/core.py`) usa `transaction.on_commit`: solo se envía si la transacción se confirmó. `hooks.on_route_created` ejecuta `customer.notify_route_scheduled` (a los clientes con correo en `Order.recipient_email`) y `staff.notify_route_assigned` (al conductor, si ya tiene uno asignado). Cada envío queda en `NotificationLog`.

Dos precisiones que importan para la tesis:

- El orden de las paradas sale del algoritmo genético, una metaheurística: no garantiza el óptimo global del problema de visita (NP-difícil), aunque con 8 paradas encontró el óptimo de fuerza bruta en todas las pruebas (`test_finds_brute_force_optimum_with_8_stops`) y en las 30 instancias del experimento igualó a OR-Tools; sí se garantiza que cada tramo es óptimo (A* y Dijkstra dan el mismo costo, probado en `test_search.py::test_e1_astar_equals_dijkstra_all_pairs_all_profiles`).
- Los minutos de cada tramo se calculan con el tráfico de la franja en que ese tramo se recorre, no solo con el de la hora de salida.
- `departure_options` ("¿a qué hora conviene salir?", 7 franjas × 2 variantes) usa vecino más cercano + 2-opt para no correr 14 genéticos por solicitud; la ruta que se guarda siempre la ordena el genético.
- Las respuestas de `POST /api/v2/routes/plan/` y `POST /api/routes/optimize/` incluyen `response_seconds`, el **tiempo real de respuesta** medido en el servidor.

### 5.2 Recálculo ante un bloqueo

1. **Reporte.** El conductor (`frontend/src/pages/driver/ReportIncident.tsx`) o el despacho hace `POST /api/traffic/incidents/` (`frontend/src/lib/incidents.ts`) con tipo, tramos (por id de arista o pares de códigos de nodo, con `both_directions` opcional), efecto y ruta de origen.
2. **Vista.** `incident_views.api_incidents` permite los 3 roles y llama a `incidents.create_incident` (`logistics/application/incidents.py`).
3. **Crear el incidente.** `create_incident` valida el tipo (`traffic`, `accident`, `landslide`, `closure`), los tramos (máximo 20 por incidente, `MAX_EDGES_PER_INCIDENT`) y el efecto (`_parse_effect`: `closure` bloquea; los demás usan un multiplicador, con tope `MAX_MULTIPLIER = 50` y piso 1). Dentro de una transacción crea `Incident`, le asocia las aristas, programa `later(on_incident_reported, ...)` (aviso a administradores y despachadores) y llama a `recompute_routes`.
4. **Pesos con incidente.** `recompute_routes` obtiene `incident_penalties` (aristas con incidente vigente) y, por cada franja necesaria, construye los pesos base con `graph.weights(TIME, ...)` y los penalizados con `routing.incidents.apply_penalties` (multiplica por `m ≥ 1` o pone infinito si está bloqueada). Calcula `compute_v_max` con los pesos **sin** incidente, que sigue siendo cota válida porque los pesos solo suben.
5. **Qué rutas revisa.** Rutas `planned` o `in_progress` con salida de hoy en adelante. Solo se recalculan los **tramos pendientes** (`_pending_leg_indexes`) y solo si algún tramo pendiente usa una arista penalizada. El orden de las paradas no cambia.
6. **A\* con incidente.** Para cada tramo pendiente afectado: el costo actual (`cost_now`, con la penalización; si pasa por una arista bloqueada se usa `BLOCKED_MINUTES = 9999`) y el costo de la ruta nueva con `astar(graph, penalized, origin, target, v_max=v_max)`. El reloj avanza tramo a tramo, sumando el tiempo de servicio.
7. **Propuesta.** Si el ahorro es al menos `MIN_SAVING_MIN = 1.0` minuto (o la ruta actual está bloqueada), se marcan como `expired` las propuestas pendientes anteriores de esa ruta y se crea una `RerouteProposal` con `current_minutes`, `proposed_minutes`, `proposed_legs` y un resumen legible (`_summary`, p. ej. "Nueva ruta por X: −N min"). Se programa `later(on_reroute_pending, proposal.id)`, que avisa al despachador que creó la ruta. Si no hay camino alterno, la ruta se lista en `unreachable_routes`.
8. **Decisión.** `POST /api/reroutes/<id>/decision/` (`incident_views.api_reroute_decision`) llama a `incidents.decide_reroute` con `decision` igual a `accept` o `keep`. Solo puede decidir el conductor de esa ruta o el despacho. Con `accept`, `_apply_proposal` reemplaza los tramos pendientes en `Route.legs`, recalcula `driving_minutes`, `total_km`, `expanded_nodes` y `finish_at`, y actualiza la ETA de las paradas pendientes; la propuesta pasa a `accepted`.
9. **Aviso al conductor.** Si fue aceptada, `later(on_reroute_approved, ...)` ejecuta `staff.notify_reroute_approved`, que envía al conductor asignado el correo "Tu ruta cambió" (`templates/emails/staff_reroute_approved.*`).

Observaciones: la aprobación puede darla el propio conductor, no solo el coordinador; así lo implementa `decide_reroute` y lo prueba `test_incidents.py::test_only_route_driver_or_dispatch_can_decide`. El recálculo ocurre en el momento de reportar el incidente; en `main` no existe una tarea periódica que lo repita (`recompute_routes` solo se invoca desde `create_incident`).

---

## 6. Pantallas

Fuente: `frontend/src/App.tsx` (router) y `frontend/src/components/layout/AppShell.tsx`. "Despacho" = `admin` o `dispatcher`.

| URL | Rol | Archivo | Función |
|---|---|---|---|
| `/login` | Público | `pages/Login.tsx` | Inicio de sesión; botones de demostración si `demo_login` está activo |
| `/seguimiento/:token` | Público (sin cuenta) | `pages/tracking/TrackingPage.tsx` | El cliente final ve el estado de su pedido con el enlace del correo |
| `/cambiar-contrasena` | Cualquier rol con sesión | `pages/account/ChangePasswordPage.tsx` | Cambio de contraseña; obligatorio con la temporal |
| `/` | Despacho | `pages/Home.tsx` | "Hoy": resumen, mapa, monitoreo en vivo, incidentes y recálculos por decidir |
| `/pedidos` | Despacho | `pages/orders/OrdersPage.tsx`, `NewOrderSheet.tsx` | Lista y alta de pedidos (dirección con Places/Geocoder) |
| `/planificar` | Despacho | `pages/planner/PlannerPage.tsx` | Planificación por zona: compara la ruta más rápida y la más corta, hora de salida y confirmación |
| `/rutas` | Despacho | `pages/routes/RoutesPage.tsx` | Lista de rutas |
| `/rutas/:routeId` | Despacho | `pages/routes/RouteDetailPage.tsx` | Detalle, asignación (`AssignmentSection`), cancelación, comprobación de tráfico en vivo (`LiveCheck`). En la sección plegable "Tramos" indica qué algoritmo ordenó las paradas ("Orden de visita: algoritmo genético · cada tramo con A*") |
| `/rutas/:routeId/imprimir` | Despacho | `pages/routes/RoutePrintPage.tsx` | Hoja de ruta para imprimir (fuera del `AppShell`) |
| `/analisis` | Despacho | `pages/analysis/AnalysisLayout.tsx` | Redirige a `laboratorio` |
| `/analisis/laboratorio` | Despacho | `pages/lab/LabPage.tsx` | Compara Dijkstra con A* y anima su expansión |
| `/analisis/trafico` | Despacho | `pages/traffic/TrafficPage.tsx` | Perfil de tráfico por franja y tipo de día |
| `/analisis/reportes` | Despacho | `pages/reports/ReportsPage.tsx` | Resultados de los experimentos (lee los CSV) |
| `/monitoreo`, `/laboratorio`, `/trafico`, `/reportes` | Despacho | `App.tsx` | Redirecciones a las pantallas nuevas |
| `/configuracion/*` | Despacho entra; solo `admin` ve el contenido | `pages/settings/SettingsPage.tsx`, `FleetSheets.tsx` | Pestañas `bodegas`, `pilotos`, `camiones`, `usuarios`. Un despachador ve el aviso "Solo el administrador puede cambiar la configuración" |
| `/conductor` | Conductor | `pages/driver/DriverTodayPage.tsx` | Rutas del día, iniciar ruta, ubicación compartida |
| `/conductor/paradas/:stopId` | Conductor | `pages/driver/DriverStopPage.tsx` | Detalle de la parada: marcar entregada o no entregada (con motivo) |
| `/conductor/navegar` y `/conductor/navegar/:stopId` | Conductor | `pages/driver/DriverNavigatePage.tsx` | Navegación dentro de la aplicación: mapa, posición en vivo, tarjeta de parada, aviso de ruta alternativa |
| Cualquier otra ruta | Con sesión de despacho | `pages/Placeholder.tsx` (`NotFoundPage`) | Página no encontrada |

**Rendimiento de los mapas (corregido el 2026-10-14).** Todas las pantallas con mapa se trababan: cada una pedía la geometría de toda la red (258 tramos, 444 726 puntos, 1 MB) en 11 consultas a la base de datos, y la capa «Nuestro tráfico» volvía a decodificar ese megabyte en cada render porque una memorización (`useMemo`) dependía de un arreglo nuevo en cada render. Ahora el servidor simplifica la geometría una sola vez (Douglas-Peucker, tolerancia de unos 11 m, `logistics/application/road_geometry.py`), la guarda en memoria y la entrega en una sola solicitud (`/api/routing/geometry/?all=1`, 41 121 puntos, 171 KB); el navegador la decodifica una vez. Además, Planificar espera 400 ms a que termine la selección antes de pedir el plan, y A* memoriza su `v_max` por lista de pesos. Prueba: `test_road_geometry.py`.

Si un usuario entra a una pantalla de otro rol, `RequireSession` lo redirige a la inicial de su rol (`homeFor`). Con contraseña temporal solo puede ir a `/cambiar-contrasena`.

---

## 7. Pruebas, métricas guardadas y experimentos

### 7.1 Inventario de pruebas

**Backend (Django, `logistics/tests/`)**: 39 archivos `test_*.py`, 388 casos según Django (339 anteriores, 30 del genético, OR-Tools y el experimento, 8 de la geometría de los mapas y 11 del tráfico en vivo).

| Clase | Archivos (casos) |
|---|---|
| Unitarias del motor | `test_search.py` (13: Dijkstra y A*, E1 con todos los pares y franjas, consistencia de la heurística, `v_max`, instrumentación), `test_multistop_api.py` (15), `test_traffic.py` (11), `test_traffic_breakdown.py` (1), `test_graph_models.py` (10), `test_geometry.py` (5), `test_road_class.py` (10), `test_regions.py` (2), `test_codes.py` (1), `test_experiments.py` (13) |
| Construcción de datos del grafo y comandos | `test_build_graph.py` (17), `test_seed_graph.py` (9), `test_check_google.py` (4), `test_preparar.py` (2), `test_archive_legacy.py` (3) |
| Integración de la API | `test_planning_api.py` (5), `test_orders_api.py` (5), `test_assignment_api.py` (15), `test_dispatch_api.py` (11), `test_driver_api.py` (10), `test_fleet_api.py` (22), `test_incidents.py` (27: penalizaciones, bloqueo, propuestas, aceptar/mantener, permisos), `test_positions.py` (8), `test_live_traffic.py` (11), `test_tracking.py` (6), `test_routing_roles.py` (3) |
| Seguridad y sesión | `test_app_session.py` (18), `test_login_limits.py` (15), `test_password_change.py` (13), `test_csp.py` (8), `test_json_requests.py` (2) |
| Correos | `test_notifications.py` (23), `test_staff_notifications.py` (19), `test_email_design.py` (2) |
| Mapas y tráfico en vivo | `test_road_geometry.py` (8: simplificación dentro de la tolerancia, red completa en una respuesta ligera, sin consultas repetidas a la base, caché que sigue los cambios del grafo, `v_max` memorizado), `test_live_planning.py` (11: minutos y llegadas de Google en vivo, hora futura enviada a Google, caché, respaldo ante falla, demora, falta de llave y tope diario, ruta guardada con su fuente, 50 paradas en menos de 30 s, las pruebas nunca llaman a Google) |
| Algoritmo genético y experimento de la tesis (RUT-79) | `test_genetic.py` (18: operadores válidos, 2-opt asimétrico, óptimo de fuerza bruta con 8 paradas, nunca peor que vecino más cercano + 2-opt, misma semilla = mismo resultado, 50 paradas en menos de 30 s, aptitud dependiente del tiempo, planificador y ruta guardada con el genético, parámetros del administrador, solo biblioteca estándar), `test_baseline_ortools.py` (2), `test_thesis_experiment.py` (10: 30 pares, reparto 4/3/3 por franja, mismos puntos en los tres escenarios, unidades y fórmula de reducción, cierre con alternativa, reproducibilidad, estadística) |

**Frontend (Vitest, `frontend/src/**/*.test.ts`)**: 28 archivos de prueba y 124 casos según Vitest (lógica pura: `lib/*.test.ts` más `components/map/markerPick.test.ts`). No hay pruebas de componentes de React ni pruebas de extremo a extremo (no hay archivos `.test.tsx` ni dependencias de Testing Library o Playwright en `package.json`).

**Cómo ejecutarlas**

- Backend: `DATABASE_URL= .venv/Scripts/python.exe manage.py test --noinput` (con `DATABASE_URL` vacío para usar SQLite; `matplotlib` de `requirements-dev.txt` para las de gráficas).
- Frontend: `cd frontend && npx vitest run` (o `npm test`).

### 7.2 Resultado real de la ejecución (2026-10-14)

| Suite | Resultado | Duración |
|---|---|---|
| Django (`manage.py test`, SQLite local) | **388 pruebas, OK, 0 fallos** | 290.7 s |
| Vitest | **28 archivos, 124 pruebas, todas aprobadas** | 10.7 s |

Aparece una advertencia de Django (`UserWarning: No directory at: ...\staticfiles\`) que no afecta el resultado.

### 7.3 Métricas que guarda el sistema

| Métrica | Dónde se guarda | Cómo se calcula |
|---|---|---|
| `driving_minutes` | `Route.driving_minutes` | Suma de minutos de los tramos con el tráfico de la franja de cada tramo |
| `total_km` | `Route.total_km` | Suma de km de los tramos |
| `shortest_minutes` | `Route.shortest_minutes` | Minutos de la ruta más corta (por km) con el mismo tráfico |
| `expanded_nodes` | `Route.expanded_nodes` | Nodos expandidos por la matriz (Dijkstra) más los tramos (A*); se suma lo de cada recálculo aceptado |
| `minutes_saved` | **No es columna.** Se calcula en `planning.route_payload` como `shortest_minutes - driving_minutes`, y en `plan_route` antes de guardar | Es la medida del "ahorro frente a la ruta más corta" |
| `elapsed_ms` | **No se guarda en `Route`.** Existe en `SearchResult` (`instrument.py`, `perf_counter`) y se escribe en los CSV de E2 y E7 | Milisegundos de una búsqueda |
| `RouteSample` | Tabla | Respuesta cruda de Google (duración con y sin tráfico, distancia, estado) para auditar cada peso del grafo |
| `TrafficProfile.multiplier` | Tabla | Multiplicador `m ≥ 1` por arista, franja y tipo de día |
| `RerouteProposal` | Tabla | `current_minutes`, `proposed_minutes`, propiedad `minutes_saved` |
| `VehiclePosition` | Tabla | Traza GPS de la ruta en curso |
| `NotificationLog` | Tabla | Auditoría de correos |
| `optimizer` | `Route.optimizer` | Algoritmo que ordenó las paradas: `genetic` (por defecto), `nn2opt` o `fixed`; vacío en rutas anteriores al cambio |
| `traffic_source`, `traffic_queried_at` | `Route.traffic_source`, `Route.traffic_queried_at` y la respuesta de planificar y de `optimize` | Fuente de los minutos: `google_tiempo_real` (Google en vivo, con la hora de la consulta) o `perfil_calibrado` (multiplicadores por franja) |
| `response_seconds` | **No se guarda**; viaja en la respuesta de planificar y de `optimize` | Tiempo real de respuesta del servidor (`perf_counter`) |
| `data_source` | `Route.data_source` y columna de cada CSV | Procedencia: `edges=google;traffic=google_routes`, o `edges=estimate;traffic=synthetic` |

El tiempo de respuesta del servidor se mide en cada solicitud de planificación (`response_seconds`), pero no se guarda. El "porcentaje de reducción frente a la ruta convencional" lo calcula el experimento de la tesis (sección 7.6) y queda en `matriz_comparativa.csv`; no es un campo de `Route`.

**Observación importante sobre documentación existente.** `docs/trazabilidad-objetivos.md` menciona `Route.distance_km`, `Route.elapsed_ms` y `static/logistics/app.js`. Ninguno existe en el código actual (`Route` tiene `total_km` y no tiene `elapsed_ms`; la carpeta `static/logistics/` solo contiene `brand`). Ese documento describe una etapa anterior y no debe usarse como fuente para el capítulo sin corregirlo.

### 7.4 Experimentos E1 a E7

Comando: `python manage.py run_experiments [--only e1 ... e7] [--out DIR] [--max-nodes N] [--reps N] [--quick] [--no-charts] [--with-google] [--yes] [--e4-trips N] [--refresh]` (`logistics/management/commands/run_experiments.py`). Escribe CSV (y PNG si hay `matplotlib`) en `experiments/output/` por defecto. Esa carpeta está en `.gitignore`: **no viaja con el repositorio**.

| Experimento | Qué mide (`logistics/routing/experiments.py`) | Archivo de salida |
|---|---|---|
| E1 | Correctitud: costo(A*) = costo(Dijkstra) en todos los pares y los 16 conjuntos de pesos (sin tráfico, 14 perfiles y km, según `weight_sets`) | `e1_correctitud.csv` |
| E2 | Eficiencia: nodos expandidos y ms de ambos, en dos perfiles (sin tráfico y pico de la mañana laboral); `reps` repeticiones y mediana de ms | `e2_eficiencia.csv` |
| E3 | Impacto del tráfico: ruta más rápida contra más corta entre las 22 cabeceras, en 14 perfiles | `e3_impacto_trafico.csv` |
| E4 | Precisión: el motor contra Google (error porcentual absoluto medio, MAPE) en 50 viajes de semilla fija; **solo con respuestas de Google en caché o con `--with-google`** | `e4_precision.csv`, `e4_resumen.csv` |
| E5 | Varias paradas: orden de captura contra vecino más cercano contra 2-opt, con 5, 10, 15 y 20 paradas, 30 instancias cada una, semilla 2026 | `e5_varias_paradas.csv` |
| E6 | Hora de salida: el mismo viaje en las 14 combinaciones de franja y tipo de día, en 4 pares fijos | `e6_hora_de_salida.csv` |
| E7 | Escalabilidad: grafos sintéticos (cuadrícula y geométrico) de 1 000, 10 000 y 100 000 nodos, 20 consultas | `e7_escalabilidad.csv` |

**Escenarios y repeticiones.** Los experimentos no están organizados en "normal, congestionamiento, cierre de vía". Lo que existe: perfiles de tráfico (14), repeticiones de medición de ms (`--reps`, por defecto 5; 3 en la corrida de abajo), 30 instancias aleatorias en E5 y 20 consultas por tamaño en E7. Los escenarios de congestionamiento y de cierre de vía se cubren como **pruebas automatizadas** de incidentes (`test_incidents.py`: `test_congestion_creates_proposal_with_savings`, `test_closure_blocks_edge_and_route_avoids_it`, `test_block_makes_route_avoid_the_edge`), no como un experimento con 10 repeticiones.

#### 7.4.1 CSV encontrados en el repositorio local (archivos del 2 de octubre, no versionados)

Los archivos de `experiments/output/` llevan `data_source = edges=google;traffic=google_routes` (E7 usa `synthetic-grid` y `synthetic-geometric`). Eso es lo que declaran los datos; en este informe no se pudo verificar la procedencia más allá de esa columna porque la base local no tiene la caché `RouteSample` de Google. Resumen calculado por mí a partir de los CSV (108 nodos, 260 aristas):

| Experimento | Resultado | Lectura |
|---|---|---|
| E1 | 184 896 de 184 896 consultas con igual costo (16 conjuntos de pesos × 11 556 pares); diferencia máxima 0.0 | A* devuelve el costo exacto de Dijkstra |
| E2 | 23 112 consultas. Nodos expandidos promedio: Dijkstra 38.2, A* 30.6 (A* expande 19.7 % menos). Milisegundos promedio: Dijkstra 0.033, A* 0.073. Mismo costo en el 100 % | A* expande menos nodos, pero en este grafo pequeño tarda más milisegundos porque calcular la heurística cuesta más de lo que ahorra |
| E3 | 6 468 casos (462 pares × 14 perfiles). La ruta más rápida difiere de la más corta en 1 923 casos (29.7 %). Ahorro máximo 213.2 min. Entre los casos que cambian: ahorro promedio 49.5 min, equivalente en promedio al 9.0 % de los minutos de la más corta | Con datos de Google, el tráfico sí cambia la mejor ruta en cerca de un tercio de los casos |
| E4 | MAPE global **38.13 %** en 50 viajes, sesgo +38.13 % (el motor sobreestima la duración de Google). Por franja: madrugada 31.6 %, pico mañana 32.7 %, media mañana 40.3 %, mediodía 36.8 %, tarde 45.5 %, pico tarde 44.4 %, noche 39.7 % | El objetivo que imprime el comando es menor a 20 % (`run_experiments.py`). **No se cumple en esos archivos.** El pendiente se registra en `docs/SEGURIDAD.md` (RUT-43) |
| E5 | 120 instancias. Mejora de 2-opt sobre el orden de captura: 31.2 % (5 paradas), 46.9 % (10), 59.0 % (15), 60.9 % (20); promedio global 49.5 %. Mejora de 2-opt sobre vecino más cercano: 2.7 %, 7.3 %, 9.1 %, 9.7 % | El orden de captura es una referencia arbitraria; la mejora sobre el vecino más cercano es modesta |
| E6 | 56 filas (4 viajes × 14 perfiles) | Tiempo del mismo viaje según la hora de salida |
| E7 | Mismo costo en todas las consultas. Nodos expandidos promedio (Dijkstra / A*): cuadrícula 1 024 nodos 620 / 342, 10 000 nodos 4 249 / 2 058, 99 856 nodos 38 191 / 17 441; geométrico 1 000 nodos 465 / 228, 10 000 nodos 5 365 / 2 983, 100 000 nodos 50 263 / 27 455. Milisegundos promedio a 100 000 nodos: cuadrícula 61.1 / 58.3, geométrico 175.7 / 175.2 | A* expande alrededor de la mitad de los nodos; en tiempo de reloj la ventaja solo aparece en los grafos grandes. Son grafos sintéticos |

#### 7.4.2 Corrida propia de hoy con datos estimados y sintéticos

Se ejecutó, con SQLite local y sin red (`DATABASE_URL` vacío): `seed_graph_nodes`, `build_graph --estimate`, `calibrate_traffic --synthetic` y `run_experiments --no-charts --max-nodes 10000 --reps 3 --out <carpeta temporal>`. Duración total del comando: 46.7 s. E4 se omitió (no hay respuestas de Google en la caché). Después se restauró `db.sqlite3` a su estado anterior.

**ADVERTENCIA (regla de `CLAUDE.md`): `data_source = edges=estimate;traffic=synthetic`. Estos números son datos de ejemplo para probar la canalización. NO son resultados de tesis y no deben citarse como tales.** El propio comando lo imprime: "ATENCIÓN: datos estimados/sintéticos. Sirven para probar, NO para el documento de tesis."

| Experimento | Resultado de la corrida de ejemplo |
|---|---|
| E1 | 184 896 de 184 896 consultas con costo(A*) = costo(Dijkstra) (100 %) |
| E2 | 23 112 consultas. Nodos expandidos promedio: Dijkstra 55.0, A* 20.9 (62.1 % menos). Milisegundos promedio: Dijkstra 0.091, A* 0.116 |
| E3 | 97 de 6 468 casos con ruta distinta; ahorro máximo 44.9 min; ahorro promedio global 0.13 min |
| E4 | Omitido (sin respuestas de Google) |
| E5 | Mejora de 2-opt sobre el orden de captura: 33.7 % (5 paradas), 47.3 % (10), 59.7 % (15), 61.4 % (20); promedio global 50.5 % |
| E6 | 4 viajes; tiempo mínimo 62 min (Ciudad de Guatemala a Escuintla, noche laboral), máximo 548 min (Ciudad de Guatemala a Flores, pico de la tarde laboral) |
| E7 | Hasta 10 000 nodos: 1 000 nodos 465 / 228 expandidos (geométrico); 1 024 nodos 620 / 342 (cuadrícula); 10 000 nodos 4 807 / 2 521 (promedio de ambos tipos); mismo costo en todas |

Comparación útil: con datos estimados y sintéticos, A* expande 62 % menos nodos que Dijkstra y casi no hay cambios de ruta por tráfico (97 casos); con los archivos que declaran datos de Google, la reducción de nodos es 19.7 % y los cambios de ruta son 1 923 casos. Las conclusiones dependen fuertemente de los datos, por eso la fuente se imprime en cada fila.

### 7.5 De dónde sale cada métrica que la tesis podría citar

| Métrica | Existe en el código | Origen |
|---|---|---|
| Correctitud de A* frente a Dijkstra | Sí | E1 y la prueba `test_search.py::test_e1_astar_equals_dijkstra_all_pairs_all_profiles` |
| Reducción de nodos expandidos de A* | Sí | E2 (`e2_eficiencia.csv`), `lab.ts::savingPct`, y en vivo en Análisis, Laboratorio |
| Tiempo de procesamiento de la búsqueda | Sí, en milisegundos por búsqueda | `SearchResult.elapsed_ms` → E2 y E7. No se guarda por ruta |
| Reducción de tiempo por tráfico (más rápida contra más corta) | Sí | `minutes_saved` (`planning.py`) y E3 |
| Reducción de distancia y de tiempo frente a la ruta convencional | Sí | `run_thesis_experiment` (`matriz_comparativa.csv`, `estadistica.json`); sección 7.6 |
| Éxito de la ruta alternativa ante cierre de vía | Sí | Escenario `cierre` del experimento de la tesis |
| Genético contra OR-Tools | Sí | `genetico_vs_ortools.csv` |
| Precisión frente a Google (MAPE) | Sí, si hay respuestas de Google | E4 (`e4_resumen.csv`) |
| Tiempo de respuesta del servidor | Sí | `response_seconds` en la API y `tiempo_respuesta_s` en el experimento (incluye 50 paradas) |

### 7.6 Experimento de la tesis: ruta convencional contra ruta optimizada (3 escenarios × 10 repeticiones)

Comando: `python manage.py run_thesis_experiment` (`logistics/routing/thesis_experiment.py`). Corrida del 2026-10-14 sobre el **grafo real de producción** (Neon, solo lectura): 108 nodos y 258 aristas activas; `data_source = edges=google;traffic=google_routes` (aristas y multiplicadores por franja de Google Routes API, sin datos sintéticos). Resultados versionados en `docs/Capitulo V/resultados/` (`matriz_comparativa.csv`, `genetico_vs_ortools.csv`, `estadistica.json`) y analizados en `experiments/colab/analisis_estadistico.ipynb` (ejecutado, con salidas).

**Diseño (según los Caps. II y III de la tesis).**

- **Ruta convencional:** proximidad sucesiva. Desde la bodega, siempre al punto **geográficamente** más cercano al anterior (línea recta), sin considerar el tráfico; cada tramo por el camino más corto en km. Sus minutos se miden con el tráfico real de la franja, como los viviría el mensajero.
- **Ruta optimizada:** el algoritmo genético ordena las paradas con la matriz de minutos con tráfico (aptitud dependiente del tiempo) y A* traza cada tramo.
- Las dos rutas usan **el mismo conjunto de puntos, el mismo grafo y la misma franja** (el "mismo instante" de la tesis se interpreta como las mismas condiciones de la vía en la misma ejecución). Ambas evitan la terracería, como la aplicación.
- **Tres corredores interdepartamentales desde la Ciudad de Guatemala:** Occidente (CA-1, hacia Quetzaltenango), Sur (CA-9/CA-2, hacia Retalhuleu) y Atlántico (CA-9, hacia Puerto Barrios). Cada instancia tiene 12 puntos de entrega tomados de los departamentos del corredor, con regreso a la bodega y 10 min de servicio por parada.
- **Escenarios:** tráfico normal (perfil de la franja); congestionamiento en la ruta principal del corredor (multiplicador ×2.5 en ambos sentidos); cierre de un tramo de la ruta principal (se quita del grafo y se mide si A* encuentra la ruta alternativa).
- **Repeticiones:** 10 por escenario: 4 en pico matutino (08:00), 3 en valle (10:30) y 3 en pico vespertino (18:30) de un martes. La repetición *i* usa los mismos puntos en los tres escenarios. Semilla 2026.
- **Estadística:** Shapiro-Wilk sobre las diferencias; t pareada si son normales, si no Wilcoxon (unilateral: la optimizada es menor); d de Cohen pareada; α = 0.05. Regla de la tesis: se rechaza H0 si p < 0.05 **y** la reducción media de distancia es ≥ 15 %.

**Resultados (30 pares).**

| Escenario | Distancia: convencional → optimizada (km, media) | Reducción de distancia | Tiempo: convencional → optimizada (min, media) | Reducción de tiempo |
|---|---|---|---|---|
| Tráfico normal | 805.74 → 753.89 | 6.49 % (t pareada, p = 0.0024, d = 1.18) | 1 261 → 1 131 | 9.89 % (t pareada, p = 0.0016, d = 1.27) |
| Congestionamiento en ruta principal | 805.74 → 837.12 | **−5.25 %** (la optimizada recorre más km para esquivar la congestión; p = 0.894, no significativo) | 2 271 → 1 779 | **20.35 %** (t pareada, p = 0.0007, d = 1.43) |
| Cierre de vía con ruta alternativa | 903.12 → 845.52 | 5.67 % (t pareada, p = 0.011, d = 0.88) | 1 409 → 1 246 | 10.93 % (t pareada, p = 0.0011, d = 1.33) |
| **Total (30 pares)** | **838.20 → 812.18** | **2.30 %** (Shapiro p = 0.277, t pareada, **p = 0.030**, d = 0.36) | **1 647 → 1 385** | **13.72 %** (Shapiro p < 0.001, Wilcoxon, **p < 0.001**, d = 0.97) |

En los 30 pares la ruta optimizada fue **más rápida** que la convencional. La distancia bajó en 18 pares, quedó igual en 3 y subió en 9 (6 del escenario de congestionamiento y 3 del normal).

**Metas de la tesis (reportadas tal cual, sin ajustar datos).**

| Meta | Resultado | ¿Se cumple? |
|---|---|---|
| Reducción de distancia ≥ 15 % | 2.30 % en promedio (6.49 % en normal, 5.67 % en cierre, −5.25 % en congestionamiento) | **No** |
| Reducción de tiempo ≥ 20 % | 13.72 % en promedio; solo el escenario de congestionamiento la alcanza (20.35 %) | **No** en el total; sí en congestionamiento |
| Rutas alternativas exitosas > 90 % | 100 % (10 de 10 cierres; A* encontró la alternativa en 0.017 s como máximo) | **Sí** |
| Tiempo de respuesta < 30 s | Máximo 2.41 s, medido con **50 paradas** (2.21 s en pico matutino, 1.41 s en valle, 2.41 s en pico vespertino); 0.6 s como máximo en las instancias de 12 paradas | **Sí** |
| Decisión sobre H0 (distancia) | p = 0.030 < 0.05, pero la reducción media (2.30 %) es menor que 15 % | **H0 no se rechaza** según la regla de la tesis |

**Lectura.** El genético optimiza el **tiempo** (su aptitud es el tiempo total estimado), no la distancia. Por eso la reducción de tiempo es significativa en los tres escenarios, mientras que la de distancia es pequeña y, ante congestión, negativa: la ruta rápida rodea el tramo congestionado aunque sume kilómetros. Además, la proximidad sucesiva geográfica ya es una referencia razonable en distancia para puntos de un mismo corredor. La meta de distancia de 15 % no se alcanza con este diseño, y así debe reportarse.

**Genético contra OR-Tools (línea base, mismas 30 instancias, misma matriz).** El genético igualó el costo de OR-Tools en las **30 de 30** instancias (diferencia media 0.000 %). Tiempo medio: genético 146 ms; OR-Tools 10 002 ms (agota su límite de 10 s con búsqueda local guiada).

### 7.7 Refuerzo exploratorio (TensorFlow / Keras)

Cuaderno `experiments/colab/refuerzo_exploratorio.ipynb` (ejecutado con TensorFlow 2.19.1, guardado con salidas). Usa el grafo real exportado con `python manage.py export_graph_json` y el mismo `genetic.py` del sistema.

- **Episodio:** bodega en la capital, 8 paradas de un corredor, una franja (pico matutino, valle o pico vespertino) y un evento aleatorio sobre la ruta planificada: congestión de ×1.5 a ×4 en 4 tramos, o cierre de un tramo (25 %). El reporte de la gravedad trae ruido de ±40 %.
- **Acciones (4 rutas candidatas):** genético sin ver el evento; genético replanificado con el evento reportado; convencional; genético por km.
- **Recompensa:** −(minutos + 0.5 · km), con los minutos del evento real.
- **Agente:** red densa de Keras (64-64) con política tipo DQN, ε-greedy y repetición de experiencias; 1 200 episodios de entrenamiento × 6 épocas y 300 de prueba no vistos.

| Política (300 episodios de prueba) | Minutos (media) | km (media) | Elige la mejor candidata |
|---|---|---|---|
| Agente DQN (Keras) | 1 168.6 | 690.1 | 53.0 % |
| Siempre el genético replanificado | **1 157.6** | 693.6 | 84.0 % |
| Siempre el genético sin ver el evento | 1 290.3 | 704.4 | 9.0 % |
| Siempre la convencional | 1 331.5 | 740.2 | 1.7 % |
| Oráculo (información perfecta) | 1 154.2 | 688.6 | 100 % |

**Resultado (reportado tal cual):** el agente de refuerzo **no supera** al genético replanificado: queda 11 min por encima en promedio. El genético que recibe el reporte del evento ya está a solo 3.4 min del oráculo, así que queda poco que aprender con esta información. El aporte del componente exploratorio es mostrar que replanificar con el evento (lo que hace el sistema) es mucho mejor que ignorarlo (−132.7 min) y que la ruta convencional (−173.9 min). Limitaciones: una sola decisión por episodio (bandido contextual), 8 paradas, tráfico por franja y eventos simulados sobre el grafo real.

---

## 8. Cumplimiento de la tesis (actualizado tras RUT-79)

La tesis aprobada es la especificación: "Python en Google Colab, scikit-learn, TensorFlow para aprendizaje por refuerzo exploratorio, OR-Tools como línea base, algoritmo genético como motor principal, máximo 50 puntos por ruta, 3 escenarios (normal, congestionamiento, cierre de vía) × 10 repeticiones". El 2026-10-14 se corrigió el código para cumplirla, conservando el grafo, Dijkstra, A*, el tráfico por franja, los incidentes, la interfaz y el despliegue.

| Afirmación de la tesis | Estado en el código | Dónde |
|---|---|---|
| Algoritmo genético como motor principal | **Cumple.** Ordena las paradas del planificador y de `/api/routes/optimize/` por defecto; parámetros ajustables por el administrador | `logistics/routing/genetic.py`, `multistop.py`, `OptimizerSettings` (sección 1.3) |
| OR-Tools como línea base | **Cumple**, solo en el experimento (no en producción) | `baseline_ortools.py`, `genetico_vs_ortools.csv` (sección 7.6) |
| TensorFlow para aprendizaje por refuerzo exploratorio | **Cumple** como cuaderno exploratorio ejecutado | `experiments/colab/refuerzo_exploratorio.ipynb` (sección 7.7) |
| Python en Google Colab | **Cumple para el análisis:** los dos cuadernos corren en Colab. El sistema en sí es una aplicación web Django + React desplegada en Render | `experiments/colab/` |
| SciPy, Pandas y NumPy para la estadística | **Cumple** | `analisis_estadistico.ipynb`, `thesis_experiment.statistics_report` |
| scikit-learn | **No se usa:** ningún paso del diseño lo necesita (la estadística usa SciPy y el refuerzo usa TensorFlow) | Sugerencia: quitar la mención o decir que no fue necesario |
| Máximo 50 puntos por ruta y respuesta < 30 s | **Cumple:** `MAX_STOPS = 50`; con 50 paradas el servidor responde en 2.4 s como máximo (`response_seconds`) | `planning.py`, `routing.py`, `test_fifty_stops_well_under_thirty_seconds` |
| 3 escenarios × 10 repeticiones (pico matutino, valle, pico vespertino) | **Cumple** | `run_thesis_experiment` (sección 7.6) |
| Ruta convencional = proximidad sucesiva | **Cumple** | `thesis_experiment.conventional_order` |
| Matriz comparativa exportable | **Cumple** como CSV del experimento (`matriz_comparativa.csv`, se abre en Excel). La interfaz no cambió: no hay botón de exportar en pantalla | `docs/Capitulo V/resultados/` |
| Tráfico del momento al planificar | **Cumple (híbrido):** minutos y llegadas con Google en vivo; orden con perfiles calibrados | `live_planning.py`, `Route.traffic_source` |
| El administrador ajusta los parámetros del genético | **Cumple** en `/admin/` de Django; no se agregó pantalla nueva en React para no cambiar la interfaz | `OptimizerSettings` |
| Metas: distancia ≥ 15 %, tiempo ≥ 20 %, alternativas > 90 %, respuesta < 30 s | Alternativas (100 %) y respuesta (2.4 s) **se cumplen**. Distancia (2.30 %) y tiempo (13.72 %) **no se cumplen** en el total; el tiempo sí en congestionamiento (20.35 %) | Sección 7.6. **Se reporta sin ajustar datos** |

**Diferencias que siguen abiertas y deben declararse en el documento:**

- **Tráfico "del momento": cumple en modo híbrido (desde el 2026-10-14).** Al planificar y al confirmar, Google mide en vivo cada tramo de la ruta (sección 1.3) y los minutos y llegadas salen de ese tráfico; la ruta guarda la fuente y la hora de la consulta. El orden de las paradas lo decide el genético con los perfiles calibrados, no con una matriz en vivo, por costo: la matriz completa costaría unos US$961 al mes con 12 paradas y US$8 830 con 50 (20 planificaciones diarias). Medido con Google real: 1.42 s con 12 paradas y 2.45 s con 50.
- **Costo del híbrido** (tarifa oficial de Compute Routes Pro: 5 000 consultas gratis al mes y US$10 por 1 000 después): hasta 26 consultas por planificación con 12 paradas (dos variantes de 13 tramos; los tramos compartidos y la confirmación salen de la caché) y hasta 102 con 50 paradas. Con 20 planificaciones diarias: unos US$106 al mes con 12 paradas y unos US$562 con 50, menos el nivel gratuito. La recalibración de los domingos usa otra SKU (Compute Route Matrix Pro, unos 15 600 elementos al mes).
- **"Mismo instante".** Se interpretó como las mismas condiciones de la vía (mismo grafo y misma franja) dentro de la misma ejecución.
- **Ventanas de tiempo de entrega y precisión de la ETA mayor a 85 %:** no se implementaron. La precisión frente a Google medida en E4 es un MAPE de 38.13 % (sección 7.4.1).
- **Hipótesis de distancia:** con la regla de la tesis (p < 0.05 y reducción ≥ 15 %), H0 no se rechaza: p = 0.030, pero la reducción es 2.30 %.

Otras diferencias detectadas durante el análisis y relevantes para el capítulo:

- Los CSV de `experiments/output/` (E1–E7) no están versionados; los del experimento de la tesis sí (`docs/Capitulo V/resultados/`).
- `docs/SEGURIDAD.md` y `rutasia/settings.py` no coinciden en HSTS, redirección HTTPS y validación de `SECRET_KEY`: verificar el estado real antes de describir la seguridad en la tesis.

---

## Fuentes en el código

Archivos consultados para este informe:

- Configuración y despliegue: `CLAUDE.md`, `requirements.txt`, `requirements-dev.txt`, `runtime.txt`, `render.yaml`, `Procfile`, `.env.example` (solo nombres de variables), `rutasia/settings.py`, `rutasia/urls.py`, `rutasia/middleware.py`, `rutasia/csp.py` (búsqueda de la cabecera), `frontend/package.json`.
- Documentación: `docs/PLAN.md` (encabezados y filas citadas), `docs/SEGURIDAD.md`, `docs/EMPEZAR.md` (DNS), `docs/GOOGLE_KEYS.md`, `docs/trazabilidad-objetivos.md`.
- Modelos y URL: `logistics/models.py`, `logistics/urls.py`.
- Presentación: `logistics/presentation/app_views.py`, `orders_views.py`, `dispatch_views.py`, `assignment_views.py`, `driver_views.py`, `fleet_views.py`, `incident_views.py`, `live_views.py`, `position_views.py`, `routing_views.py`, `password_views.py`, `tracking_views.py`, `serializers.py`.
- Aplicación: `logistics/application/planning.py`, `routing.py`, `incidents.py`, `driver.py`, `fleet.py`, `login_limits.py`, `live_traffic.py`, `dispatch.py`, `notifications/core.py`, `notifications/hooks.py`, `notifications/staff.py`, `notifications/transport.py`, `notifications/customer.py`.
- Dominio: `logistics/domain/notifications.py`.
- Motor: `logistics/routing/dijkstra.py`, `astar.py`, `graph.py`, `multistop.py`, `genetic.py`, `baseline_ortools.py`, `thesis_experiment.py`, `traffic.py`, `incidents.py`, `instrument.py`, `geo.py`, `google.py`, `experiments.py`.
- Comandos: `logistics/management/commands/run_experiments.py`, `run_thesis_experiment.py`, `export_graph_json.py`, `refresh_traffic.py` (más `--help` de `calibrate_traffic` y `build_graph`).
- Cuadernos: `experiments/colab/analisis_estadistico.ipynb` y `refuerzo_exploratorio.ipynb` (ejecutados el 2026-10-14).
- Pruebas: los 39 archivos de `logistics/tests/test_*.py` (conteo de casos y nombres citados) y los 28 archivos `frontend/src/**/*.test.ts`.
- Frontend: `frontend/src/App.tsx`, `components/layout/AppShell.tsx`, `components/map/NetworkMap.tsx`, `lib/googleMaps.ts`, `lib/places.ts`, `lib/geocode.ts`, `lib/roads.ts`, `lib/planning.ts`, `lib/incidents.ts`, `lib/lab.ts`, `pages/settings/SettingsPage.tsx`.
- Datos y ejecuciones: `experiments/output/*.csv` (resumen propio), y ejecuciones del 2026-10-14 de `manage.py test`, `npx vitest run` y `manage.py run_experiments` (con datos estimados y sintéticos, salida en carpeta temporal).
- Búsquedas con `grep` sobre todo el proyecto: `genetic|genético|ortools|or-tools|sklearn|scikit|tensorflow|reinforcement|torch|networkx|osmnx|colab`; `distancematrix|geocode/json|maps/api/`; `SECURE_|HSTS`; `MAX_STOPS`; `later(`; `recompute_routes`.
