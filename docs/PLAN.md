# Plan de rediseño — Rutas inteligentes con tráfico para paquetería en Guatemala

> Proyecto de graduación · Plan de trabajo a 3 semanas
> Estado: **planificación** (aún no se modifica código)

---

## 1. Visión

En Guatemala **la ruta más corta casi nunca es la más rápida**. Salir de la capital hacia Quetzaltenango puede tardar 1 hora más a las 7:00 que a las 10:00, y un tramo corto con un tranque puede costar más que un desvío largo. El sistema responde a esta pregunta:

> *"Dado el tráfico a la hora en que voy a salir, ¿cuál es la mejor ruta para llevar mis paquetes por Guatemala?"*

El núcleo del proyecto es **Dijkstra y A\* implementados y usados correctamente** sobre una **red vial nacional** (todo Guatemala), cuyas aristas pesan **tiempo** (no kilómetros). Ese tiempo sale de **Google Maps con tráfico** y cambia según la hora y el día. Encima del motor va una aplicación moderna por roles: el despachador planifica y el conductor entrega.

### Decisiones tomadas

| # | Decisión | Resultado |
|---|----------|-----------|
| 1 | **Núcleo algorítmico** | **Dijkstra + A\*** propios, con pesos de tiempo según tráfico |
| 2 | **Cobertura** | **Todo Guatemala** (red nacional, como la versión actual) |
| 3 | **Datos viales y de tráfico** | **Google Maps APIs**: sin descargar mapas de calles, así el servidor en Render usa muy poca memoria |
| 4 | Objetivo | Proponer la **ruta más rápida considerando el tráfico** y compararla con la más corta |
| 5 | Alcance | Varias paradas por ruta |
| 6 | Frontend | **React** (SPA) + API de Django, con estilo **minimalista** |
| 7 | Conductor | Rol propio con vista móvil |
| 8 | Nombre | Nuevo desde cero (§12) |
| 9 | Plazo | ~3 semanas |

### Reparto de trabajo: nuestro motor vs. Google

| Lo hace **nuestro motor** (el aporte de la tesis) | Lo hace **Google Maps** (datos y dibujo) |
|---|---|
| Decidir **por qué nodos pasar** (Dijkstra / A\*) | Dar la **duración con y sin tráfico** de cada tramo |
| Decidir el **orden de las paradas** | Autocompletar y geocodificar direcciones |
| Estimar la hora de llegada con el perfil de tráfico | **Dibujar** el recorrido real por carretera entre los nodos elegidos |
| Comparar "más corta" vs "más rápida" | Mapa base |

### Lo que cambia respecto a la versión actual

| Hoy | Nueva versión |
|-----|---------------|
| 10 departamentos y 13 conexiones con km escritos a mano | Red nacional de **~100–150 nodos** (cabeceras, municipios clave y cruces de carreteras), con aristas verificadas por Google |
| Peso = km fijos | Peso = **minutos**, según la franja horaria (tráfico) |
| A\* y Dijkstra dan lo mismo y no se mide nada | Cada algoritmo tiene un rol (§2.6) y se miden nodos explorados y tiempo |
| La UI siempre usa Dijkstra | Se elige y se compara; hay un laboratorio visual |
| Google Directions traza la ruta | Google **solo dibuja** la secuencia de nodos que eligió nuestro algoritmo (se reutiliza `fetchRoadGeometryGoogleMaps`) |

---

## 2. Núcleo: Dijkstra y A\* con tráfico

### 2.1 Modelo del problema (grafo nacional)

- **Nodos (~100–150):**
  - Las 22 cabeceras departamentales.
  - Municipios con mucha actividad logística.
  - **Cruces de carreteras** (p. ej. Los Encuentros, Cuatro Caminos, El Rancho, Cocales, La Ruidosa, Río Hondo, Palín, San Lucas Sacatepéquez).
  - Salidas de la capital (Periférico, CA-9 Sur, CA-9 Norte, CA-1 Oeste).
- **Aristas dirigidas:** tramos de carretera entre nodos vecinos (CA-1, CA-2, CA-9, CA-10, CA-13, CA-14, RN…). Cada tramo lo verifica Google con una ruta real.
- **Atributos de cada arista `e`:**
  - `L_e`: km por carretera (de Google).
  - `t0_e`: minutos sin tráfico (`staticDuration`).
  - `m_e(franja, tipo_de_día)`: multiplicador de tráfico ≥ 1.
- **Memoria:** unos pocos cientos de aristas; cabe en KB. Se guarda en PostgreSQL (se extiende el modelo `RouteConnection` que ya existe) y se carga a memoria al iniciar.

### 2.2 Función de costo: tiempo con tráfico

```
costo(e, t) = t0_e × m_e(franja(t), tipo_de_día(t))        (en minutos)
m_e ≥ 1  →  1.0 = sin tráfico, 2.0 = tarda el doble
```

- Como `m ≥ 1`, **los pesos nunca son negativos**. Es un requisito de Dijkstra y de A\*.
- Los **incidentes** (accidente, derrumbe, manifestación, cierre) multiplican aún más, o bloquean la arista (`costo = ∞`) durante una ventana de tiempo.

### 2.3 Datos de tráfico con Google (sin descargar mapas)

**1. Construir el grafo** (script, una vez)
- Se definen los nodos con sus coordenadas.
- Se proponen aristas con cada nodo y sus *k* vecinos más cercanos.
- Google **Routes API** (`computeRouteMatrix`) confirma que hay carretera y da `L_e` y `t0_e`.
- Se descartan las aristas redundantes (las que pasan por otro nodo del grafo).

**2. Perfiles de tráfico por franja horaria** (script por lotes, se repite cada semana)

| Franja | Horario |
|--------|---------|
| Madrugada | 05:00–07:00 |
| **Pico mañana** | 07:00–09:00 |
| Media mañana | 09:00–12:00 |
| Mediodía | 12:00–14:00 |
| Tarde | 14:00–17:00 |
| **Pico tarde** | 17:00–20:00 |
| Noche | 20:00–05:00 |

- 7 franjas × 2 tipos de día (laboral y fin de semana) = 14 perfiles.
- Para cada arista y perfil se consulta la matriz con `departureTime` futuro y `routingPreference = TRAFFIC_AWARE_OPTIMAL`:
  ```
  m_e = duration / staticDuration
  ```
- Con ~300 aristas × 14 perfiles son ~4,200 elementos por calibración. Se guardan en BD y **no se vuelven a pedir en cada búsqueda**.

**3. Refinamiento en vivo** (Should)
- Al planificar para *ahora*, se piden a Google las duraciones actuales **solo de las aristas de la ruta candidata y sus alternativas cercanas**.
- Se actualizan y se re-ejecuta A\*. Pocas consultas por planificación, con caché de 10–15 minutos.

**4. Validación del modelo**
- Se compara el tiempo que estima nuestro motor contra el de Google para la ruta completa en ~50 viajes a distintas horas.
- Se reporta el **error porcentual medio (MAPE)**.

> ⚠️ No se "leen" datos de la capa visual de tráfico de Google Maps: sus condiciones de uso no lo permiten. Todo sale de las APIs de rutas, que es el uso legítimo.

### 2.4 Dijkstra — el algoritmo exacto de referencia

- **Qué hace:** expande los nodos en orden de **tiempo acumulado** `g(n)` desde el origen, con cola de prioridad (min-heap).
- **Complejidad:** `O((V + E) log V)`.
- **Correcto aquí** porque todos los pesos son ≥ 0.
- **Dos modos de uso:**
  - **Punto a punto:** se detiene al sacar el destino.
  - **Uno a todos:** una corrida da el tiempo desde un origen a **todos** los nodos. Es la forma eficiente de construir la matriz de tiempos entre paradas (§2.7).

### 2.5 A\* — la búsqueda guiada

- **Qué hace:** expande en orden de `f(n) = g(n) + h(n)`, donde `h(n)` estima el tiempo que falta.
- **Heurística correcta para costos en tiempo:**
  ```
  h(n) = haversine(n, destino) / v_max
  ```
- **Cómo se elige `v_max` para que A\* sea óptimo** (clave para la tesis):
  ```
  v_max = max sobre todas las aristas de  haversine(u, v) / costo_mínimo(u, v)
  ```
  - `costo_mínimo(u, v)` es el tiempo de esa arista en su franja **más rápida**.
  - Con `v_max` calculado así **desde los datos de Google**, se cumple para toda arista `haversine(u,v) / v_max ≤ costo(u,v)`.
  - Junto con la desigualdad triangular, eso hace la heurística **consistente**: `h(u) ≤ costo(u,v) + h(v)`.
  - Y **admisible**: nunca sobreestima.
- **Consecuencias:**
  - Cada nodo se cierra una sola vez.
  - A\* devuelve **exactamente el mismo costo que Dijkstra** explorando menos nodos.
- **Desempate:** con `f` iguales se prefiere el mayor `g`.
- *Extensión opcional:* **ALT** (A\* con puntos de referencia). Con 22 cabeceras como puntos de referencia da una heurística más informada que sigue siendo admisible.

### 2.6 Qué algoritmo se usa para qué

| Necesidad | Algoritmo | Por qué |
|-----------|-----------|---------|
| Matriz de tiempos entre bodega y paradas | **Dijkstra uno-a-todos** | N corridas en vez de N² búsquedas |
| Ruta entre dos puntos (planificar un tramo) | **A\*** | Un destino y una buena heurística: explora menos |
| Recalcular por un incidente o el refinamiento en vivo | **A\*** | Respuesta inmediata |
| "¿A qué hora conviene salir?" | **A\*** en cada franja | Una consulta por franja |
| Validación | **Dijkstra** | Referencia exacta: A\* debe dar el mismo costo |
| Laboratorio (defensa) | **Ambos, lado a lado** | Mostrar la diferencia en nodos explorados |

### 2.7 Varias paradas

1. Cada dirección se geocodifica con Google Places y se asocia a su **nodo más cercano** del grafo (su municipio o cruce).
2. **Matriz de tiempos** entre bodega y paradas con Dijkstra uno-a-todos, para la franja de salida.
3. **Orden de visita** con vecino más cercano + **2-opt**, minimizando el **tiempo total**.
4. Cada tramo entre paradas con **A\***. La hora de llegada a una parada es la hora de salida del siguiente tramo, así que el tráfico se evalúa en la franja correcta de cada tramo.
5. El dibujo en el mapa y la "última milla" dentro de la ciudad destino los traza **Google Directions** usando como *waypoints* los nodos que eligió nuestro algoritmo.

*El reparto de paradas entre varios vehículos (VRP) queda como Could.*

### 2.8 Tráfico dependiente del tiempo (avanzado)

- **Base (Must):** cada tramo usa la franja en la que **empieza**.
- **Avanzado (Should):** cada arista usa la franja en la que el vehículo **llega a ella**.
  - Es importante en viajes largos: si sales a las 6:30, llegas a la capital en hora pico.
  - Dijkstra y A\* siguen siendo correctos si se cumple **FIFO** (salir más tarde nunca hace llegar antes).
  - Con franjas escalonadas FIFO puede romperse en los cambios de franja. Se evita con el modelo de velocidades por intervalos de **Ichoua, Gendreau y Potvin (2003)**.

### 2.9 Checklist de uso correcto

- [ ] Pesos ≥ 0 (el tráfico **multiplica** por ≥ 1, nunca resta).
- [ ] **Misma unidad** en costo y heurística: minutos con minutos.
- [ ] `v_max` **calculado desde los datos** (§2.5), no inventado ni el promedio.
- [ ] No redondear la heurística hacia arriba. *El código actual usa `ROUND_HALF_UP` en `haversine_km` (`logistics/domain/services.py:29`); hay que truncar o usar `float`.*
- [ ] Grafo **dirigido**: los tiempos de ida y vuelta pueden diferir por el tráfico (entrar a la capital en la mañana ≠ salir).
- [ ] Cola con *lazy deletion* y conjunto de cerrados (ya existe en el código actual).
- [ ] Grafo **en memoria**; las consultas a Google nunca se hacen dentro del bucle del algoritmo.
- [ ] Prueba automática: en todos los pares de nodos y todas las franjas, `costo(A*) == costo(Dijkstra)`.
- [ ] Reportar **nodos expandidos** como métrica principal. En un grafo de ~150 nodos los milisegundos son muy pequeños: medir con el promedio de muchas repeticiones.

### 2.10 Experimentos para el documento de tesis

| # | Experimento | Métrica | Resultado esperado |
|---|-------------|---------|--------------------|
| E1 | Correctitud | % de pares y franjas con costo(A\*) = costo(Dijkstra) | 100 % |
| E2 | Eficiencia | Nodos expandidos por A\* vs Dijkstra, por distancia de la consulta | A\* expande menos, sobre todo en viajes largos |
| E3 | Impacto del tráfico | Tiempo de la ruta más corta (km) vs la más rápida, por franja | En pico, la "rápida" ahorra X min y a veces cambia de carretera |
| E4 | Precisión | MAPE de nuestro estimado vs Google en la ruta completa | Idealmente < 20 % |
| E5 | Varias paradas | Tiempo total: orden de captura vs vecino más cercano vs + 2-opt | 2-opt mejora el orden inicial |
| E6 | Hora de salida | Tiempo del mismo viaje en cada franja | Curva con picos de mañana y tarde |
| E7 | Escalabilidad | Nodos expandidos y ms en grafos sintéticos de 1,000 a 100,000 nodos | La ventaja de A\* crece con el tamaño del grafo |

> E7 usa grafos generados (cuadrículas y grafos geométricos aleatorios), así se demuestra la escalabilidad **sin gastar memoria en producción**: corre en tu computadora, no en Render.

Todo se genera con `python manage.py run_experiments` → CSV + gráficas para el documento.

---

## 3. Roles y permisos

| Módulo | Administrador | Despachador | Conductor |
|--------|:---:|:---:|:---:|
| Inicio / KPIs | ✅ | ✅ | — |
| Pedidos | ✅ | ✅ | — |
| Planificador de rutas | ✅ | ✅ | — |
| Rutas / viajes | ✅ | ✅ | — |
| Monitoreo en vivo + incidentes | ✅ | ✅ | — |
| Tráfico por franja horaria | ✅ | ✅ | — |
| **Laboratorio Dijkstra vs A\*** | ✅ | ✅ | — |
| Flota | ✅ | ✅ (ver) | — |
| Reportes | ✅ | ✅ | — |
| Configuración (usuarios, bodegas, nodos, calibración de tráfico) | ✅ | — | — |
| **Mi ruta de hoy / marcar entregas** | — | — | ✅ |
| **Reportar incidente** | — | — | ✅ |
| **Aviso de ruta alternativa** | — | — | ✅ |

---

## 4. Alcance (MoSCoW)

### Must
- Grafo nacional (~100–150 nodos) construido y verificado con Google.
- Perfiles de tráfico por franja horaria (14 perfiles) calibrados con Google.
- **Dijkstra y A\*** propios con pesos en tiempo y el checklist de §2.9 completo.
- Comparación **más rápida (tráfico)** vs **más corta (km)** en el Planificador.
- Varias paradas: Dijkstra para la matriz, vecino más cercano + 2-opt, A\* por tramo, ETAs.
- **Laboratorio**: Dijkstra y A\* lado a lado sobre el mapa de Guatemala.
- Experimentos E1, E2, E3, E5 y E7.
- Pedidos con dirección real (Google Places) asociada al nodo más cercano.
- Vista del conductor y login por rol.

### Should
- Refinamiento en vivo con duraciones actuales de Google (§2.3.3).
- Tráfico dependiente del tiempo con FIFO (§2.8).
- Mapa de tráfico por franja con control deslizante.
- "¿A qué hora conviene salir?" (E6).
- Incidentes + recálculo con A\* + aviso al conductor.
- Validación contra Google (E4).

### Could
- ALT con las cabeceras como puntos de referencia.
- Reparto de paradas entre varios vehículos (VRP).
- Modo oscuro, exportar hoja de ruta en PDF.

### Won't (por ahora)
- Grafo de calles de cada ciudad.
- App nativa.
- Multi-empresa.

---

## 5. Arquitectura técnica

| Capa | Tecnología |
|------|-----------|
| Frontend | React + Vite + TypeScript, Tailwind CSS + shadcn/ui, React Router, TanStack Query |
| Mapa | `@vis.gl/react-google-maps`: mapa base, recorridos de Google Directions, nodos explorados del laboratorio |
| Gráficas | Recharts |
| Backend | Django como API JSON |
| **Motor de rutas** | **Python puro** (`heapq`), sin librerías de ruteo: el algoritmo es nuestro |
| Datos viales y de tráfico | Google Routes API (matrices por lotes y refinamiento en vivo), Places API, Directions (dibujo) |
| BD | PostgreSQL (Neon) |
| Deploy | Render, un solo servicio. **Memoria mínima**: el grafo son unos cientos de aristas |

### Estructura del motor

```
logistics/
└── routing/
    ├── graph.py         # carga nodos/aristas de BD a listas de adyacencia en memoria
    ├── traffic.py       # franja(t), multiplicadores m_e, incidentes
    ├── dijkstra.py      # punto a punto y uno-a-todos
    ├── astar.py         # A* con v_max derivado de los datos
    ├── multistop.py     # matriz, vecino más cercano, 2-opt, ETAs
    ├── google.py        # cliente Routes API con caché (nunca se llama dentro del algoritmo)
    └── instrument.py    # nodos expandidos, ms, orden de exploración
logistics/management/commands/
├── build_graph.py       # nodos → aristas candidatas → verificación con Google
├── calibrate_traffic.py # 14 perfiles por arista
└── run_experiments.py   # E1–E7 → CSV + gráficas
```

### Endpoints nuevos

| Endpoint | Uso |
|----------|-----|
| `POST /api/routing/route` | origen, destino, hora de salida, algoritmo, criterio (tiempo/km) → ruta, minutos, km, nodos expandidos |
| `POST /api/routing/compare` | Dijkstra vs A\*, y más rápida vs más corta, en una sola respuesta |
| `POST /api/routing/explore` | orden de exploración de nodos (para animar el laboratorio) |
| `POST /api/routes/optimize` | varias paradas → orden, tramos, ETAs |
| `GET /api/traffic/profile?band=peak_am&day=weekday` | multiplicadores por arista para el mapa de tráfico |
| `POST /api/traffic/incidents` | reportar incidente |
| `GET /api/routing/best-departure` | tiempo estimado por franja de salida |

---

## 6. Cambios al modelo de datos

| Modelo | Cambio |
|--------|--------|
| `Department` → **`Node`** | Se generaliza: cabecera, municipio o cruce (`kind`), coordenadas, departamento al que pertenece |
| `RouteConnection` → **`Edge`** | + `duration_free_min` (sin tráfico), `distance_km` de Google, carretera (CA-1…), fecha de verificación. **Dirigida** |
| `TrafficProfile` (nuevo) | arista, franja, tipo de día → multiplicador `m`, fecha y fuente de calibración |
| `Incident` (nuevo) | tipo, arista(s) o ubicación, multiplicador o bloqueo, inicio/fin, quién reportó |
| `Depot` (nuevo) | bodega: nombre, dirección, coordenadas, nodo |
| `Order` | + destinatario, teléfono, dirección, `place_id`, coordenadas, nodo |
| `Trip` → **`Route`** | + hora de salida, algoritmo, criterio, **minutos con tráfico**, km, **nodos expandidos**, comparación contra la ruta más corta |
| `RouteStop` (nuevo) | ruta, pedido, secuencia, ETA, estado, motivo, hora de entrega |
| `Driver` | + `user` (OneToOne) |
| `UserProfile.Role` | `admin`, `dispatcher`, `driver` |

Los datos actuales (10 departamentos, 13 conexiones con km a mano) se reemplazan por el grafo construido con `build_graph`.

---

## 7. Pantallas

### Despachador / Administrador (escritorio, minimalista)

| Pantalla | Contenido clave |
|----------|-----------------|
| **Inicio** | Franja de tráfico actual, rutas en curso, retrasos, pedidos sin asignar |
| **Pedidos** | Tabla, filtros, selección múltiple, alta con autocompletado de dirección |
| **Planificador** ⭐ | Mapa de Guatemala; hora de salida; **"Más rápida" vs "Más corta"**; ETAs; ahorro en minutos |
| **Laboratorio** ⭐ | Mapa de Guatemala dividido: **Dijkstra | A\***. Animación de nodos explorados; contadores de nodos, ms y costo (idéntico); selector de franja para ver cómo cambia la ruta |
| **Tráfico** | Red nacional coloreada por multiplicador según la franja elegida; curva "mejor hora para salir" |
| **Rutas** | Lista y detalle: paradas, línea de tiempo, estimado vs real |
| **Monitoreo** | Rutas en curso, incidentes, avisos de recálculo |
| **Reportes** | Minutos ahorrados, puntualidad, resultados de los experimentos |
| **Configuración** | Usuarios, bodegas, nodos del grafo, calibración de tráfico (última fecha, re-ejecutar) |

### Conductor (móvil)
- **Mi ruta de hoy:** paradas en orden con ETA según el tráfico.
- **Detalle de parada:** navegar, llamar, entregado / no entregado.
- **Aviso de ruta alternativa:** *"Tránsito pesado en CA-9 Sur. Nueva ruta por Palín: −18 min"* → Aceptar / Mantener.
- **Reportar:** tráfico, accidente, derrumbe, carretera cerrada.

*(El prototipo del lienzo cubre Planificador, Pedidos y Conductor en estilo minimalista. Falta: el mapa del Planificador a escala nacional, el Laboratorio, el mapa de Tráfico y el aviso de ruta alternativa.)*

---

## 8. Flujos estrella

### A. Planificar con tráfico
1. Elegir bodega, **hora de salida** y pedidos (p. ej. entregas en Chimaltenango, Quetzaltenango y Retalhuleu).
2. **Optimizar:** Dijkstra arma la matriz, 2-opt ordena y A\* elige los tramos.
3. Resultado: *"Más rápida: 5 h 10 min por CA-1 · La más corta (por CA-2) tardaría 5 h 55 min con el tráfico de las 07:00"*.
4. Sugerencia: *"Si sales a las 09:00, ahorras 40 min"*.
5. Confirmar y asignar al conductor.

### B. Laboratorio (para la defensa)
1. Elegir origen y destino en el mapa de Guatemala (p. ej. Ciudad de Guatemala → Flores) y una franja.
2. **Ejecutar:** los dos algoritmos animan su exploración al mismo tiempo.
3. Dijkstra se expande hacia todos lados (también hacia la costa sur y occidente); A\* avanza hacia el norte. Mismo costo, menos nodos.
4. Cambiar a "Pico mañana" y ver cómo la ruta cambia de carretera.

### C. Recálculo en vivo
1. Se reporta un derrumbe o tranque en un tramo.
2. Ese tramo se penaliza o bloquea y A\* recalcula los tramos pendientes.
3. El conductor recibe el aviso con los minutos que ahorra.

---

## 9. Sistema de diseño (minimalista)

- **Estilo:** fondo casi blanco, sin sombras pesadas, sin tarjetas dentro de tarjetas, separadores de 1 px en lugar de cajas, mucho espacio en blanco.
- **Principios:** el mapa es protagonista · los números del algoritmo siempre visibles (tiempo, km, nodos, ms) · una acción principal por pantalla · todo estado tiene diseño (vacío, cargando, error, éxito).
- **Tipografía:** una sola familia (**Geist**) y **Geist Mono** para cifras, horas y códigos. Jerarquía por tamaño y peso, no por color.
- **Color con propósito:** interfaz en neutros. Acción principal en **negro** (`#111113`). El color se reserva para **rutas, tráfico y estados**.
- **Tokens base:** fondo `#FAFAF9` · superficie `#FFFFFF` · texto `#111113` · texto secundario `#6B6F76` · línea `#ECECEA` · acento `#2F4BD8` · éxito `#1A7F4B` · error `#B42318` · tránsito pesado `#F3C4AE`.
- **Escala de congestión:** secuencial de un solo tono, de claro a oscuro según `m`, legible para personas con daltonismo. Nunca solo verde/rojo.
- **Algoritmos:** Dijkstra y A\* con dos tonos que también difieren en luminosidad. Nodos explorados = puntos translúcidos; ruta final = línea gruesa.
- **Mapa base de Google** con estilo desaturado (vía *Map ID*) para que las rutas destaquen.
- **Navegación:** barra lateral clara, sin barra superior; búsqueda global con ⌘K.
- **Estados como punto + texto** (sin "pastillas" de color).
- **Accesibilidad:** contraste AA, teclado, objetivos táctiles ≥ 44 px en la vista del conductor.

---

## 10. Cronograma (3 semanas)

### Semana 1 — Motor de rutas (el corazón de la tesis)
| Día | Entregable |
|-----|-----------|
| 1 | Lista de nodos (cabeceras, municipios clave, cruces) con coordenadas; modelos `Node`, `Edge`, `TrafficProfile` |
| 2 | `build_graph` con Google (aristas verificadas, `t0`, km); `graph.py` en memoria |
| 3 | Dijkstra (punto a punto y uno-a-todos) + A\* con `v_max` derivado; corregir el redondeo; **E1** |
| 4 | `calibrate_traffic` (14 perfiles); costos por franja; **E2, E3** |
| 5 | Varias paradas (matriz, vecino más cercano, 2-opt, ETAs) + endpoints `/api/routing/*` + **E5, E7** |

### Semana 2 — Aplicación React
| Día | Entregable |
|-----|-----------|
| 6 | Vite, Tailwind, shadcn, layout minimalista, login por rol; **probar el deploy en Render hoy** |
| 7 | Pedidos con Places y asociación al nodo más cercano |
| 8 | **Planificador** (hora de salida, más rápida vs más corta, ETAs, dibujo con Directions) |
| 9 | **Laboratorio** Dijkstra vs A\* con animación |
| 10 | Mapa de tráfico por franja + mejor hora para salir |

### Semana 3 — Conductor, tiempo real y cierre
| Día | Entregable |
|-----|-----------|
| 11 | Vista del conductor |
| 12 | Incidentes + recálculo con A\* + aviso; refinamiento en vivo |
| 13 | Rutas, Monitoreo, Inicio, Reportes |
| 14 | E4, E6; gráficas finales para el documento |
| 15 | Pulido, datos de demo, deploy final, guion de defensa, README |

> Regla: si un día se atrasa, se recorta de **Could/Should**, nunca del motor ni de E1–E3.

---

## 11. Riesgos

| Riesgo | Impacto | Mitigación |
|--------|---------|------------|
| Costo o cuota de las APIs de Google | Medio | Calibración por lotes (una vez por semana), caché en BD, refinamiento en vivo limitado a pocas aristas, alertas de presupuesto en Google Cloud |
| Grafo pequeño → poca diferencia visible entre A\* y Dijkstra | Medio | ~100–150 nodos (no 10); consultas largas en el laboratorio (capital → Petén); E7 con grafos sintéticos grandes |
| Precisión del modelo por franjas | Medio | Validar con MAPE (E4); refinamiento en vivo; documentar limitaciones |
| Condiciones de uso de Google | Medio | Solo APIs de rutas; nada de leer la capa visual de tráfico |
| API key expuesta | Medio | Key del navegador restringida por HTTP referrer; key separada para el servidor (Routes API) |
| Alcance | Alto | MoSCoW estricto; la semana 1 es el motor |

---

## 12. Nombre (pendiente de elegir)

| Nombre | Idea |
|--------|------|
| **Enruta** | "Poner en ruta" (provisional en el prototipo) |
| **Trayecta** | De *trayecto* |
| **Vértice** | Teoría de grafos: conecta con Dijkstra y A\* |
| **Rumbo** | Dirección, simple |
| **Ruvia** | Ruta + vía |

---

## 13. Pendientes que conviene decidir

- [ ] **Nombre** final.
- [ ] **Lista de nodos:** confirmar las 22 cabeceras + qué municipios y cruces incluir (se propone una lista inicial el día 1).
- [ ] **Bodega(s) de demo:** ¿una en la capital o también regionales (p. ej. Quetzaltenango)?
- [ ] Título y objetivos de la tesis alineados con *"búsqueda de rutas óptimas con Dijkstra y A\* en la red vial de Guatemala con tráfico dependiente del tiempo"*. Si el título menciona **IA**, A\* es un algoritmo clásico de búsqueda informada en IA (Russell & Norvig).
- [ ] ¿Qué métricas o formato pide el asesor para los experimentos?

---

## 14. Definición de "terminado" para la defensa

- En el **Laboratorio**, Dijkstra y A\* encuentran la **misma ruta** entre dos puntos de Guatemala y A\* explora visiblemente menos nodos.
- Al cambiar la franja de "Media mañana" a "Pico mañana", el sistema **propone otra ruta** y muestra cuántos minutos ahorra frente a la más corta.
- Un despachador planifica varias paradas con ETAs realistas.
- Un conductor recibe su ruta, reporta un incidente y recibe una ruta alternativa.
- E1, E2, E3, E5 y E7 (idealmente todos) tienen tablas y gráficas listas.
- Desplegado en Render con uso de memoria mínimo.
