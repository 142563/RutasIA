# Plan de rediseño — Rutas inteligentes con tráfico para paquetería en Guatemala

> Proyecto de graduación · Plan de trabajo a 3 semanas
> Estado: **planificación** (aún no se modifica código)

---

## 1. Visión

En Guatemala, sobre todo en el área metropolitana, **la ruta más corta casi nunca es la más rápida**. Una misma entrega puede tardar 20 minutos a las 10:00 y 70 minutos a las 7:00. El sistema responde a esta pregunta:

> *"Dado el tráfico a la hora en que voy a salir, ¿cuál es la mejor ruta para llegar a mis entregas?"*

Para responderla, el núcleo del proyecto es **Dijkstra y A\* implementados y usados correctamente** sobre un **grafo vial real** cuyas aristas pesan **tiempo** (no kilómetros), y ese tiempo cambia según el **tráfico por hora y día**. Encima de ese motor va una aplicación moderna por roles: el despachador planifica y el conductor entrega.

### Decisiones tomadas

| # | Decisión | Resultado |
|---|----------|-----------|
| 1 | **Núcleo algorítmico** | **Dijkstra + A\*** propios, sobre un grafo vial con pesos de tiempo según tráfico |
| 2 | Objetivo del sistema | Proponer la **ruta más rápida considerando el tráfico** (y compararla con la más corta) |
| 3 | Alcance | Rutas con **varias paradas** y direcciones reales |
| 4 | Frontend | **React** (SPA) consumiendo la API de Django |
| 5 | Conductor | Rol propio con su usuario y **vista móvil** |
| 6 | Nombre | Nuevo desde cero (§12) |
| 7 | Plazo | ~3 semanas |

### Lo que cambia respecto a la versión actual

| Hoy | Nueva versión |
|-----|---------------|
| Grafo de 22 departamentos | Grafo vial real de la ciudad (miles de intersecciones) |
| Peso = km fijos | Peso = **minutos**, que varían según la hora (tráfico) |
| A* y Dijkstra dan lo mismo y no se nota diferencia (grafo muy pequeño) | La diferencia se **mide y se ve**: nodos explorados, milisegundos |
| A* existe en el backend pero la UI nunca lo usa | Cada algoritmo tiene un **rol concreto** en el sistema (§2.6) y hay un laboratorio para compararlos |
| Google traza la ruta | **Nuestro motor calcula la ruta**; Google Maps solo la dibuja y aporta datos para calibrar |

---

## 2. Núcleo: Dijkstra y A\* con tráfico

### 2.1 Modelo del problema (grafo)

- **Nodos:** intersecciones de calles del área metropolitana (Ciudad de Guatemala, Mixco, Villa Nueva, etc.), obtenidas de **OpenStreetMap**.
- **Aristas dirigidas:** tramos de calle. Respetan los **sentidos únicos**; una calle de doble vía son dos aristas.
- **Atributos de cada arista `e`:**
  - `L_e`: longitud (km).
  - `tipo_e`: clase de vía (primaria, secundaria, residencial…).
  - `v_e`: velocidad a flujo libre (km/h), según el límite o la clase de vía.
  - `corredor_e`: corredor al que pertenece (Roosevelt, Periférico, Aguilar Batres, CA-9…), si aplica.

### 2.2 Función de costo: tiempo con tráfico

```
tiempo_libre(e)   = L_e / v_e                              (en minutos)
costo(e, t)       = tiempo_libre(e) × m_e(t)
m_e(t)            = multiplicador de congestión ≥ 1, según hora y día de t
                    (1.0 = sin tráfico; 2.5 = tarda 2.5 veces más)
```

- `m_e(t)` sale del **perfil de tráfico** (§2.3) y puede aumentar por **incidentes** reportados (accidente, cierre, manifestación).
- Como `m ≥ 1`, **los pesos nunca son negativos**. Es un requisito de Dijkstra y de A\*.

### 2.3 Modelo de tráfico (de dónde salen los multiplicadores)

**1. Calibración con Google Routes API** (proceso por lotes, sin tiempo real)
- Para cada corredor principal se consulta la ruta entre sus extremos a distintas horas con `routingPreference = TRAFFIC_AWARE_OPTIMAL` y `departureTime`.
- La API devuelve `duration` (con tráfico) y `staticDuration` (sin tráfico):
  ```
  m_corredor(hora, tipo_de_día) = duration / staticDuration
  ```
- Para ~15 corredores × 24 horas × 2 tipos de día (laboral y fin de semana) son ~720 consultas, una sola vez. Cabe en el crédito gratuito de Google.

**2. Aristas sin corredor**
- Usan un multiplicador por **clase de vía y hora** (por ejemplo, una residencial en hora pico = promedio de los corredores cercanos, atenuado).

**3. Incidentes en vivo**
- El despachador o el conductor reportan un incidente sobre el mapa.
- Las aristas cercanas reciben un multiplicador extra, o se bloquean (`m = ∞`) durante una ventana de tiempo.

> ⚠️ No se "leen" datos de la capa de tráfico de Google Maps: sus condiciones de uso no lo permiten. La calibración usa la API de rutas, que sí es legítima.

**Validación del modelo.** Se comparan los tiempos estimados por nuestro motor contra los de Google en ~50 viajes aleatorios a distintas horas y se reporta el **error porcentual medio (MAPE)**. Es un resultado directo para la tesis.

### 2.4 Dijkstra — el algoritmo exacto de referencia

- **Qué hace:** expande los nodos en orden de **tiempo acumulado** `g(n)` desde el origen, usando una cola de prioridad (min-heap).
- **Complejidad:** `O((V + E) log V)` con heap binario.
- **Por qué es correcto aquí:** todos los pesos son ≥ 0 (§2.2).
- **Dos modos de uso:**
  - **Punto a punto:** se detiene al sacar el destino de la cola.
  - **Uno a todos:** se deja correr completo y da el tiempo desde un origen a **todas** las paradas en una sola ejecución. Por eso es ideal para construir la matriz de tiempos entre paradas (§2.7).

### 2.5 A\* — la búsqueda guiada

- **Qué hace:** expande los nodos en orden de `f(n) = g(n) + h(n)`, donde `h(n)` estima el tiempo que falta hasta el destino.
- **Heurística correcta para costos en tiempo:**
  ```
  h(n) = distancia_haversine(n, destino) / v_max
  v_max = velocidad máxima a flujo libre de TODO el grafo
  ```
- **Es admisible** (nunca sobreestima). Ningún vehículo puede ir más rápido que `v_max` ni recorrer menos que la línea recta, y el tráfico solo hace más lento (`m ≥ 1`).
- **Es consistente:** `h(u) ≤ costo(u,v) + h(v)` por la desigualdad triangular y porque `L_uv ≥ haversine(u,v)`. Así cada nodo se cierra **una sola vez** y A\* devuelve **exactamente el mismo costo que Dijkstra** explorando menos nodos.
- **Desempate:** con `f` iguales se prefiere el nodo con mayor `g` (el más cercano al destino). Reduce expansiones sin afectar el resultado óptimo.
- *Extensión opcional:* **ALT** (A\* con puntos de referencia y desigualdad triangular), una heurística más informada que sigue siendo admisible.

### 2.6 Qué algoritmo se usa para qué (uso correcto)

| Necesidad en el sistema | Algoritmo | Por qué |
|-------------------------|-----------|---------|
| Matriz de tiempos entre bodega y paradas | **Dijkstra uno-a-todos** (una corrida por punto) | Con N paradas son N corridas, en vez de N² búsquedas punto a punto |
| Trazar cada tramo de la ruta final | **A\*** | Un solo destino con una buena heurística: explora mucho menos |
| Recalcular en vivo por un incidente o un retraso | **A\*** | Debe responder en milisegundos |
| "¿A qué hora conviene salir?" | **A\*** repetido por hora de salida | Muchas consultas punto a punto |
| Validación y referencia | **Dijkstra** | Es el patrón de oro: A\* debe dar el mismo costo |
| Laboratorio visual (defensa) | **Ambos, lado a lado** | Mostrar la diferencia en nodos explorados |

### 2.7 Varias paradas (orden de visita)

1. Construir la **matriz de tiempos** con Dijkstra uno-a-todos desde la bodega y desde cada parada, a la hora de salida planificada.
2. Ordenar las paradas con **vecino más cercano** y mejorar el orden con **2-opt** (quita cruces), minimizando el **tiempo total**, no los km.
3. Trazar cada tramo con **A\*** y calcular la **hora estimada de llegada (ETA)** a cada parada. La hora de llegada a la parada *k* es la hora de salida del tramo *k+1*, así que el tráfico se evalúa a la hora correcta de cada tramo.
4. Con varios vehículos, el reparto de paradas entre ellos (VRP) queda como **Could**: primero cada vehículo con sus paradas asignadas.

### 2.8 Tráfico dependiente del tiempo (nivel avanzado)

- **Versión base (Must):** "foto" del tráfico. Cada búsqueda usa los multiplicadores de la hora de salida de ese tramo.
- **Versión avanzada (Should):** el costo de cada arista se evalúa a la hora en que el vehículo **llega** a ella. Dijkstra y A\* siguen siendo correctos si se cumple la **propiedad FIFO** (salir más tarde nunca hace llegar antes).
  - Los multiplicadores escalonados por hora pueden romper FIFO en el cambio de hora.
  - Se evita con el modelo de velocidades por intervalos de **Ichoua, Gendreau y Potvin (2003)**, que garantiza FIFO.

### 2.9 Errores a evitar (checklist de uso correcto)

- [ ] Pesos siempre ≥ 0 (el tráfico **multiplica** por ≥ 1, nunca resta).
- [ ] **Misma unidad** en costo y heurística: minutos con minutos. Usar km en la heurística cuando el costo está en minutos rompe la optimalidad.
- [ ] `v_max` = máxima del grafo, **no** la velocidad promedio (con el promedio la heurística sobreestima).
- [ ] No redondear la heurística hacia arriba. *El código actual usa `ROUND_HALF_UP` en `haversine_km` (`logistics/domain/services.py:29`); hay que truncar o usar `float` sin redondear.*
- [ ] Grafo **dirigido** (sentidos únicos de OSM).
- [ ] Cola con *lazy deletion* y conjunto de cerrados (ya existe en el código actual).
- [ ] Grafo cargado **en memoria** al iniciar, nunca consultas a la BD por arista.
- [ ] Prueba automática: en miles de pares aleatorios, `costo(A*) == costo(Dijkstra)`.
- [ ] Comparar siempre con el **mismo grafo y la misma hora**, y reportar **nodos expandidos** además de milisegundos.
- [ ] Ubicar cada dirección en el grafo: *snap* al nodo más cercano con un índice espacial por cuadrícula.

### 2.10 Experimentos para el documento de tesis

| # | Experimento | Métrica | Resultado esperado |
|---|-------------|---------|--------------------|
| E1 | Correctitud | % de pares donde costo(A\*) = costo(Dijkstra) | 100 % |
| E2 | Eficiencia | Nodos expandidos y ms, según la distancia de la consulta | A\* expande una fracción de lo que expande Dijkstra |
| E3 | Impacto del tráfico | Tiempo real de la ruta más corta (km) vs la más rápida (tráfico), por hora | En hora pico la ruta "rápida" ahorra X min |
| E4 | Precisión del modelo | MAPE de nuestros tiempos vs Google | Idealmente < 20 % |
| E5 | Varias paradas | Tiempo total: orden de captura vs vecino más cercano vs + 2-opt | 2-opt mejora el orden inicial |
| E6 | Hora de salida | Tiempo del mismo recorrido de 5:00 a 22:00 | Curva con picos de mañana y tarde |
| E7 | Escalabilidad | ms vs tamaño del grafo o número de paradas | Crece según la complejidad teórica |

Los resultados se generan con un comando (`python manage.py run_experiments`) que exporta CSV y gráficas para el documento.

---

## 3. Roles y permisos

| Módulo | Administrador | Despachador | Conductor |
|--------|:---:|:---:|:---:|
| Inicio / KPIs | ✅ | ✅ | — |
| Pedidos | ✅ | ✅ | — |
| Planificador de rutas | ✅ | ✅ | — |
| Rutas / viajes | ✅ | ✅ | — |
| Monitoreo en vivo + incidentes | ✅ | ✅ | — |
| Mapa de tráfico por hora | ✅ | ✅ | — |
| **Laboratorio Dijkstra vs A\*** | ✅ | ✅ | — |
| Flota | ✅ | ✅ (ver) | — |
| Reportes | ✅ | ✅ | — |
| Configuración (usuarios, bodegas, calibración de tráfico) | ✅ | — | — |
| **Mi ruta de hoy / marcar entregas** | — | — | ✅ |
| **Reportar tráfico o incidente** | — | — | ✅ |
| **Aviso de ruta alternativa** | — | — | ✅ |

El rol *supervisor* actual pasa a ser *despachador*. Un conductor es un `User` enlazado a un `Driver`.

---

## 4. Alcance (MoSCoW)

### Must
- Grafo vial real del área metropolitana (OSM) cargado en memoria.
- Perfil de tráfico por hora y tipo de día, calibrado con Google Routes API.
- **Dijkstra y A\*** propios sobre ese grafo, con pesos en tiempo y todo el checklist de §2.9.
- Ruta **más rápida con tráfico** vs **más corta en km**, comparadas en pantalla.
- Varias paradas: matriz con Dijkstra, orden con vecino más cercano + 2-opt, tramos con A\*.
- **Laboratorio**: Dijkstra y A\* lado a lado sobre el mapa, con nodos explorados, ms y costo.
- Experimentos E1–E3 y E5 automatizados.
- Pedidos con dirección real (Google Places) y *snap* al grafo.
- Vista del conductor: ruta del día, paradas en orden, marcar entregado / no entregado.
- Login y navegación por rol.

### Should
- **Mapa de tráfico** con control deslizante de hora (0–23 h).
- **"¿A qué hora conviene salir?"** (E6).
- Incidentes en vivo y **recálculo con A\*** con aviso al conductor: *"Ruta alternativa: ahorras 12 min"*.
- Tráfico dependiente del tiempo con FIFO (§2.8).
- Validación contra Google (E4) y escalabilidad (E7).
- GPS real del conductor y monitoreo en vivo.

### Could
- ALT (A\* con puntos de referencia).
- Reparto de paradas entre varios vehículos (VRP).
- Modo interurbano reutilizando el grafo actual de departamentos.
- Modo oscuro, exportar hoja de ruta en PDF.

### Won't (por ahora)
- Tráfico en tiempo real de sensores o de terceros.
- App nativa (la vista del conductor será web responsive).
- Multi-empresa.

---

## 5. Arquitectura técnica

### Stack

| Capa | Tecnología |
|------|-----------|
| Frontend | React + Vite + TypeScript, Tailwind CSS + shadcn/ui, React Router, TanStack Query, react-hook-form + zod |
| Mapa | `@vis.gl/react-google-maps` (solo dibuja: nuestras rutas, nodos explorados, capa de congestión) |
| Gráficas | Recharts |
| Backend | Django como API JSON (se mantiene) |
| **Motor de rutas** | **Python puro** (`heapq`), sin librerías de ruteo: el algoritmo es nuestro |
| Construcción del grafo | Script **offline** con OSMnx (no se instala en producción) |
| Tráfico | Script de calibración con Google Routes API; resultados guardados en BD |
| BD | PostgreSQL (Neon) |
| Deploy | Render, un solo servicio (Django sirve la API y el build de React) |

### Estructura del motor

```
logistics/
└── routing/
    ├── graph.py        # carga el grafo en memoria (listas de adyacencia compactas)
    ├── traffic.py      # multiplicadores m_e(t): perfil + incidentes
    ├── dijkstra.py     # punto a punto y uno-a-todos
    ├── astar.py        # A* con heurística admisible y consistente en tiempo
    ├── snap.py         # dirección → nodo más cercano (índice por cuadrícula)
    ├── multistop.py    # matriz de tiempos, vecino más cercano, 2-opt, ETAs
    └── instrument.py   # contadores: nodos expandidos, ms, orden de exploración
scripts/
├── build_graph.py      # OSM → grafo recortado → archivo comprimido
└── calibrate_traffic.py# Google Routes → multiplicadores por corredor y hora
logistics/management/commands/
└── run_experiments.py  # E1–E7 → CSV + gráficas
```

### API del motor (nuevos endpoints)

| Endpoint | Uso |
|----------|-----|
| `POST /api/routing/route` | origen, destino, hora de salida, algoritmo → ruta, tiempo, km, nodos expandidos, ms |
| `POST /api/routing/compare` | la misma consulta con Dijkstra y A\*, más la ruta más corta en km |
| `POST /api/routing/explore` | orden de exploración de nodos (para animar el laboratorio) |
| `POST /api/routes/optimize` | varias paradas → orden, tramos, ETAs |
| `GET /api/traffic/profile?hour=7&day=weekday` | multiplicadores para la capa de congestión |
| `POST /api/traffic/incidents` | reportar incidente |
| `GET /api/routing/best-departure` | tiempo estimado por hora de salida |

---

## 6. Cambios al modelo de datos

| Modelo | Cambio |
|--------|--------|
| `TrafficProfile` (nuevo) | corredor o clase de vía, tipo de día, hora → multiplicador `m`; fecha y fuente de calibración |
| `Corridor` (nuevo) | nombre (p. ej. Calzada Roosevelt), aristas que lo componen |
| `Incident` (nuevo) | tipo, ubicación, radio, multiplicador o bloqueo, inicio/fin, quién lo reportó |
| `Depot` (nuevo) | bodega: nombre, dirección, coordenadas, nodo del grafo |
| `Order` | + destinatario, teléfono, dirección, `place_id`, coordenadas, nodo del grafo |
| `Trip` → **Route** | + hora de salida, algoritmo, **tiempo con tráfico**, km, **nodos expandidos**, ms, comparación contra la ruta más corta |
| `RouteStop` (nuevo) | ruta, pedido, secuencia, ETA, estado, motivo, hora de entrega |
| `Driver` | + `user` (OneToOne) |
| `UserProfile.Role` | `admin`, `dispatcher`, `driver` |
| Grafo vial | **Archivo** comprimido versionado (no tablas: se carga completo en memoria) |

`Department` y `RouteConnection` se quedan como la versión 1 del proyecto (grafo interdepartamental).

---

## 7. Pantallas

### Despachador / Administrador (escritorio)

| Pantalla | Contenido clave |
|----------|-----------------|
| **Inicio** | Tráfico actual (índice de congestión), rutas en curso, retrasos, pedidos sin asignar |
| **Pedidos** | Tabla, filtros, selección múltiple; alta con autocompletado de dirección |
| **Planificador** ⭐ | Hora de salida, paradas, resultado. Comparación **"más rápida con tráfico" vs "más corta en km"**, ETA por parada y ahorro en minutos |
| **Laboratorio de algoritmos** ⭐ | Mismo origen y destino. Mapa dividido: Dijkstra a la izquierda y A\* a la derecha, **animando los nodos explorados**. Contadores de nodos expandidos, ms y costo (idéntico en ambos). Selector de hora para ver cómo cambia la ruta con el tráfico |
| **Tráfico** | Mapa de congestión por corredor con control de hora; curva "mejor hora para salir" |
| **Rutas** | Lista y detalle: paradas, línea de tiempo, estimado vs real |
| **Monitoreo** | Rutas en curso, incidentes activos, avisos de recálculo |
| **Reportes** | Minutos ahorrados vs ruta más corta, puntualidad, resultados de los experimentos |
| **Configuración** | Usuarios, bodegas, calibración de tráfico (última fecha, re-ejecutar) |

### Conductor (móvil)
- **Mi ruta de hoy:** paradas en orden con ETA según el tráfico.
- **Detalle de parada:** navegar, llamar, entregado / no entregado.
- **Aviso de ruta alternativa:** *"Hay tránsito pesado en Calzada Roosevelt. Nueva ruta: −12 min"* → Aceptar / Mantener.
- **Reportar:** tráfico pesado, accidente o calle cerrada (un toque, con la ubicación actual).

*(El prototipo actual en el lienzo cubre Planificador, Pedidos y Conductor. Falta agregar el Laboratorio, la pantalla de Tráfico y el aviso de ruta alternativa.)*

---

## 8. Flujos estrella

### A. Planificar con tráfico
1. Elegir bodega, **hora de salida** y pedidos.
2. **Optimizar:** Dijkstra construye la matriz, 2-opt ordena y A\* traza los tramos.
3. Resultado: la ruta en el mapa con ETA por parada, y la tarjeta **"Con tráfico: 1 h 12 min · La ruta más corta tardaría 1 h 38 min"**.
4. Sugerencia: *"Si sales a las 9:30 en lugar de 7:30, ahorras 25 min"*.
5. Confirmar y asignar al conductor.

### B. Laboratorio (para la defensa)
1. Elegir dos puntos en el mapa y una hora.
2. **Ejecutar:** ambos algoritmos animan su exploración al mismo tiempo.
3. Se ve que Dijkstra "se expande en círculo" y A\* "apunta al destino". Mismo costo, menos nodos.
4. Mover la hora a 7:00 y ver cómo la ruta cambia de corredor por el tráfico.

### C. Recálculo en vivo
1. Se reporta un incidente en un corredor.
2. Los multiplicadores de esas aristas suben y A\* recalcula los tramos pendientes de las rutas afectadas.
3. El conductor recibe el aviso con los minutos que ahorra.

---

## 9. Sistema de diseño

- **Estilo: minimalista.** Fondo casi blanco, sin sombras pesadas, sin tarjetas dentro de tarjetas, separadores de 1 px en lugar de cajas, mucho espacio en blanco.
- **Principios:** el mapa es protagonista · los números del algoritmo siempre visibles (tiempo, km, nodos, ms) · una acción principal por pantalla · todo estado tiene diseño (vacío, cargando, error, éxito).
- **Tipografía:** una sola familia (**Geist**) y **Geist Mono** para cifras, horas y códigos. Jerarquía por tamaño y peso, no por color.
- **Color con propósito:** interfaz en neutros. Acción principal en **negro** (`#111113`). El color se reserva para **rutas, tráfico y estados**: si algo tiene color, significa algo.
- **Tokens base:** fondo `#FAFAF9` · superficie `#FFFFFF` · texto `#111113` · texto secundario `#6B6F76` · línea `#ECECEA` · acento `#2F4BD8` · éxito `#1A7F4B` · error `#B42318` · tránsito pesado `#F3C4AE`.
- **Navegación:** barra lateral clara, sin barra superior; búsqueda global con ⌘K.
- **Estados como punto + texto** (no "pastillas" de color).
- **Escala de congestión:** secuencial de un solo tono, de claro a oscuro según `m` (1.0 → 3.0+), legible para personas con daltonismo. Nunca solo verde/rojo.
- **Colores de algoritmo** (fijos en todo el sistema): Dijkstra y A\* con dos tonos distinguibles también por luminosidad. Nodos explorados = puntos translúcidos; ruta final = línea gruesa.
- **Estados:** pendiente = gris · planificado = azul · en curso = ámbar · entregado = verde · fallido = rojo.
- **Componentes:** botón, input, combobox de dirección, badge, tabla, panel lateral, modal, toast, tarjeta de métrica, **control deslizante de hora**, **leyenda de congestión**, **contador animado**, *skeleton*, estado vacío, marcador numerado.
- **Accesibilidad:** contraste AA, teclado, objetivos táctiles ≥ 44 px en la vista del conductor.

---

## 10. Cronograma (3 semanas)

### Semana 1 — Motor de rutas (el corazón de la tesis)
| Día | Entregable |
|-----|-----------|
| 1 | Definir el área (municipios); `build_graph.py` con OSM; medir nodos, aristas y memoria |
| 2 | `graph.py` + `snap.py`; Dijkstra punto a punto y uno-a-todos con instrumentación |
| 3 | A\* con heurística en tiempo; prueba E1 (A\* = Dijkstra en miles de pares); corregir el redondeo de la heurística |
| 4 | Corredores + `calibrate_traffic.py` (Google Routes) + `TrafficProfile`; costos por hora |
| 5 | Varias paradas (matriz, vecino más cercano, 2-opt, ETAs) + endpoints `/api/routing/*` + E2, E3, E5 |

### Semana 2 — Aplicación React
| Día | Entregable |
|-----|-----------|
| 6 | Vite, Tailwind, shadcn, layout, login y ruteo por rol; **probar el deploy en Render hoy** |
| 7 | Pedidos con autocompletado de dirección y *snap* al grafo |
| 8 | **Planificador** con hora de salida, comparación con tráfico y ETAs |
| 9 | **Laboratorio** Dijkstra vs A\* con animación de exploración |
| 10 | Mapa de tráfico por hora + "mejor hora para salir" |

### Semana 3 — Conductor, tiempo real y cierre
| Día | Entregable |
|-----|-----------|
| 11 | Vista del conductor: ruta del día, paradas y entregas |
| 12 | Incidentes + recálculo con A\* + aviso de ruta alternativa |
| 13 | Rutas, Monitoreo, Inicio y Reportes |
| 14 | E4 (validación contra Google), E6, E7; gráficas para el documento |
| 15 | Pulido responsive y accesibilidad, datos de demo, deploy final, guion de la defensa, README |

> Regla: si un día se atrasa, se recorta de **Could/Should**, nunca del motor ni de los experimentos E1–E3.

---

## 11. Riesgos

| Riesgo | Impacto | Mitigación |
|--------|---------|------------|
| Grafo demasiado grande para la memoria de Render | Alto | Recortar al área metropolitana; listas compactas (arrays); medir el día 1 |
| Calidad del modelo de tráfico | Alto | Calibrar con Google, validar con MAPE (E4) y documentar limitaciones con honestidad |
| Python lento en grafos grandes | Medio | A\* reduce las expansiones; caché de matrices por hora; medir con E7 |
| Condiciones de uso de Google | Medio | Solo usar la Routes API para calibrar; nada de leer la capa de tráfico |
| Licencia de OpenStreetMap (ODbL) | Bajo | Atribución "© OpenStreetMap contributors" en el mapa y en el documento |
| API key expuesta | Medio | Restringir por HTTP referrer; key separada para el servidor |
| Alcance | Alto | MoSCoW estricto; la semana 1 es el motor, sin excepciones |

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
- [ ] **Área del grafo:** ¿solo Ciudad de Guatemala o también Mixco y Villa Nueva? A más área, más memoria.
- [ ] **Corredores** a calibrar (propuesta: Roosevelt, Periférico, Aguilar Batres, Petapa, Liberación, Las Américas, Reforma, CA-9 Norte y Sur, CA-1 hacia Mixco, Bulevar San Cristóbal…).
- [ ] Título y objetivos formales de la tesis alineados con *"búsqueda de rutas óptimas con Dijkstra y A\* en una red vial con tráfico dependiente del tiempo"*. Si el título menciona **IA**, A\* es un algoritmo clásico de búsqueda informada en IA (Russell & Norvig).
- [ ] ¿Qué métricas o formato pide el asesor para los experimentos?

---

## 14. Definición de "terminado" para la defensa

- En el **Laboratorio**, Dijkstra y A\* encuentran la **misma ruta óptima**, y A\* explora visiblemente menos nodos.
- Al cambiar la hora de 10:00 a 7:00, el sistema **propone otra ruta** por el tráfico y muestra cuántos minutos ahorra frente a la ruta más corta.
- Un despachador planifica varias paradas con ETAs realistas según el tráfico.
- Un conductor recibe su ruta en el celular, reporta un incidente y recibe una ruta alternativa.
- Los experimentos E1–E3 y E5 (idealmente todos) tienen tablas y gráficas listas para el documento.
- Todo desplegado en Render con datos de demo coherentes.
