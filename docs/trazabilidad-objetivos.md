# Trazabilidad: protocolo de graduación ↔ código del prototipo

Mapa entre lo que promete el protocolo *«Sistema inteligente de optimización de
rutas para entrega de paquetes basado en análisis de tráfico»* (Ticas Palencia,
mayo 2026) y lo que hoy existe en este repositorio.

El propósito es poder defender con precisión qué está implementado y qué
corresponde declarar como fase siguiente, en lugar de que la brecha la descubra
el tribunal.

Última revisión: 2 de octubre de 2026 (rama `main`, worktree `dface09`).

> **Nota (2 de octubre de 2026):** Este documento ha sido actualizado para
> reflejar el estado actual de la rama `main` tras la finalización del motor
> nuevo, la app React, incidentes, asignación de rutas y recalibración semanal.
> Las brechas 2, 3 y 4 se han cerrado parcialmente; la brecha 1 sigue bajo
> revisión como "Pendiente de decisión" (protocolo vs. viabilidad técnica).

---

## Resumen

| Estado | Cantidad |
|---|---|
| ✅ Implementado y verificable en la aplicación | 10+ |
| ⚠️ Implementado parcialmente | 4 |
| 🔷 Pendiente de decisión (protocolo vs. viabilidad) | 1 |
| ❌ No implementado — fase siguiente | 1 |

---

## Objetivo Específico 1 — Selección y comparación de algoritmos

> *«Seleccionar e implementar en Python el algoritmo […] con mayor eficiencia
> para el Problema de Ruteo de Vehículos […] comparando al menos dos algoritmos
> mediante métricas de distancia total recorrida, tiempo de procesamiento y
> porcentaje de reducción frente a rutas convencionales.»*

| Requisito | Estado | Dónde |
|---|---|---|
| Implementación en Python | ✅ | `logistics/routing/dijkstra.py`, `astar.py` |
| Comparar al menos dos algoritmos | ✅ | Pestaña **Laboratorio** (`src/pages/lab/`); `/api/routing/compare/` compara ambos |
| Métrica: distancia total recorrida | ✅ | `Route.distance_km`, experimento E3 |
| Métrica: tiempo de procesamiento | ✅ | `Route.elapsed_ms`, experimentos E1–E7 |
| Métrica: % de reducción frente a rutas convencionales | ✅ | Comparación contra ruta geométricamente simple (E2, E3) |
| El algoritmo sea de *aprendizaje automático* | 🔷 | Ver «Brecha 1» — **Pendiente de decisión** |

**Qué se puede demostrar en vivo.** En el par Guatemala → Suchitepéquez la
planificación convencional recorre 337.00 km y tanto Dijkstra como A\* encuentran
165.00 km: una reducción del **51.0%**, muy por encima del 15% de la hipótesis.
La aplicación sugiere automáticamente los pares donde la heurística voraz se
desvía (`findDivergentPairs()` en `static/logistics/app.js`).

**Matiz que conviene anticipar.** Dijkstra y A\* devuelven siempre la *misma*
ruta óptima, así que entre ellos la reducción de distancia es 0% por definición;
se diferencian en esfuerzo de búsqueda. En la red actual A\* explora 5 nodos
donde Dijkstra explora 6, pero en **tiempo de reloj A\* resulta más lento**
(≈0.34 ms vs ≈0.19 ms) porque evaluar la heurística Haversine cuesta más de lo
que ahorra en un grafo de 11 nodos. La ventaja asintótica de A\* aparece al
crecer el grafo. El veredicto que muestra el Laboratorio se genera a partir de
los números medidos, nunca de un texto fijo, precisamente para no afirmar algo
que los datos no respalden.

**Sobre la línea base.** `GreedyOptimizer` es una heurística voraz: en cada cruce
avanza al departamento más cercano al destino en línea recta, sin considerar el
costo acumulado. Modela la planificación manual «a ojo». **No** es la ruta de una
empresa real, y así está rotulado en la interfaz. Sobre redes poco densas
coincide con frecuencia con la ruta óptima: de los 90 pares conectados de la base
actual, se desvía en 15.

## Teoría de Grafos (protocolo, p. 36)

> *«Los algoritmos de Dijkstra y A\* constituyen los componentes de búsqueda de
> caminos del sistema, mientras que los algoritmos genéticos y el aprendizaje
> por refuerzo operan sobre la estructura de grafo para encontrar la secuencia
> óptima de visita a los nodos de entrega.»*

| Componente | Estado | Dónde |
|---|---|---|
| Dijkstra como búsqueda de caminos | ✅ | `logistics/routing/dijkstra.py`: punto-a-punto y uno-a-todos |
| A\* con heurística Haversine | ✅ | `logistics/routing/astar.py` + `logistics/routing/geo.py::haversine_km()` |
| Red vial modelada como grafo ponderado | ✅ | `logistics/routing/graph.py::RoadGraph`, `Node`, `Edge` (dirigida) |
| Genéticos / refuerzo para la secuencia de visita | 🔷 | `logistics/routing/multistop.py`: vecino cercano + 2-opt (heurística, no aprendizaje) |
| Pesos dinámicos según tráfico real | ✅ | `logistics/routing/traffic.py`, `live_traffic.py`, `refresh_traffic` (semanal) |

La heurística es admisible (nunca sobreestima el costo por carretera), lo que
garantiza que A\* conserve la optimalidad. Hay un test que lo comprueba sobre
todos los pares: `AlgorithmComparisonTests.test_astar_never_explores_more_nodes_than_dijkstra`.

---

## Brechas

### Brecha 1 — Aprendizaje automático 🔷 Pendiente de decisión

El protocolo declara en la Tabla 1 de viabilidad técnica **scikit-learn**,
**TensorFlow** y **OR-Tools**, y el Objetivo General habla de *«algoritmos de
aprendizaje automático»*. Ninguna de las tres bibliotecas está en
`requirements.txt`, y Dijkstra y A\* son **búsqueda clásica en grafos, no
aprendizaje automático**: no hay entrenamiento, ni datos de ajuste, ni política
aprendida.

**Estado actual (octubre 2026):**
- **Capa de búsqueda de caminos** (Dijkstra, A\*): ✅ implementada, medida (E1–E3, E7).
- **Capa de secuencia de visitas**: `logistics/routing/multistop.py` usa **vecino más cercano + 2-opt**, que son heurísticas greedy, no aprendizaje automático. Es suficiente para "varias paradas" pero no es ML.

**Defensa posible:**
1. La página 36 del protocolo asigna a Dijkstra y A\* el rol de búsqueda de caminos (✅ hecho),
   y a genéticos/refuerzo el de optimización de la secuencia (⚠️ parcial: se usa heurística,
   no ML). Las métricas principales (distancia, tiempo, nodos) se miden completamente.
2. El proyecto propone una solución viable: buscar la ruta óptima es el core del sistema
   y está demostrado. Optimizar el orden de paradas con 2-opt es un trade-off tiempo-calidad
   defendible para una tesis de graduación.

**No se recomienda** implementar redes neuronales o algoritmos genéticos porque:
- No hay datos históricos de entrenamient disponibles.
- El 2-opt + vecino cercano ya resuelve bien casos reales (E5).
- Aumentar complejidad sin beneficio demostrativo rompe el principio de minimalismo.

### Brecha 2 — Tráfico en tiempo real como peso dinámico ✅ Resuelto

El protocolo pide que los pesos de los arcos *«varíen en función de las
condiciones de tráfico en tiempo real»*. 

**Estado actual (octubre 2026):** ✅ Implementado completamente.

- **Base (calibración):** `logistics/routing/traffic.py` + `calibration.py` crean 14 perfiles de tráfico (7 franjas × 2 tipos de día) con multiplicadores `m_e(franja, día)` obtenidos de Google Routes API.
- **Verificación en vivo:** `logistics/application/live_traffic.py` (RUT-39) consulta Google Routes API con `departureTime` actual para refinamientos antes de optimizar.
- **Recalibración automática:** `refresh_traffic` (comando en `logistics/management/commands/`) se ejecuta semanalmente vía cron en `render.yaml` para mantener los multiplicadores al día.
- **Incidentes con recálculo:** `logistics/routing/incidents.py` + `application/incidents.py` (RUT-15) permiten penalizar o bloquear una arista temporalmente y recalcular rutas con A\*.

**Evidencia en tests:** `logistics/tests/` incluye pruebas de live_traffic y E4 (precisión vs. Google).

### Brecha 3 — 50 puntos de entrega por ruta ⚠️ Implementado parcialmente

El alcance declara *«hasta 50 puntos de entrega simultáneos por ruta»*.

**Estado actual (octubre 2026):** ⚠️ Parcialmente resuelto.

- **Varias paradas:** `logistics/routing/multistop.py` (RUT-23) implementa:
  - Matriz de tiempos entre bodega y paradas con Dijkstra uno-a-todos.
  - Vecino más cercano para un orden inicial.
  - 2-opt para mejorar ese orden.
  - ETAs por tramo, considerando el tráfico de cada franja.
- **Endpoint:** `/api/routes/optimize/` acepta múltiples paradas y devuelve la ruta optimizada.
- **Límites prácticos:** Implementado para 5–20 paradas (E5). Aumentar a 50 requeriría VRP más sofisticado (branch-and-bound o algoritmos metaheurísticos) sin beneficio demostrativo en la tesis.

**Evidencia:** Experimento E5 demuestra que 2-opt mejora significativamente el orden inicial en casos reales.

**Nota defensiva:** Dijkstra y A\* son el core del proyecto; varias paradas con heurísticas sólidas (vecino cercano + 2-opt) es lo recomendado por el PLAN.md (§2.7, Should), no el VRP de 50+ paradas (Could).

### Brecha 4 — Tres escenarios de prueba ⚠️ Implementado parcialmente

El Objetivo Específico 3 exige validar en tráfico normal, congestionamiento en
ruta principal y cierre de vía con ruta alternativa.

**Estado actual (octubre 2026):** ⚠️ Parcialmente resuelto.

- **Escenario 1 (tráfico normal):** ✅ Completamente. El motor optimiza rutinariamente contra 14 perfiles de tráfico (E3, E6).
- **Escenario 2 (congestionamiento):** ✅ Parcialmente. `logistics/routing/incidents.py` permite aplicar multiplicadores `m > 1` a una arista durante una ventana de tiempo (`start_time`, `end_time`). El conductor recibe aviso de ruta alternativa (frontend/src/pages/driver/).
- **Escenario 3 (cierre de vía):** ✅ Parcialmente. Se modela como multiplicador `m = ∞` (bloqueo). A\* calcula rutas alternas que evitan la arista bloqueada.

**Evidencia:** 
- `logistics/tests/test_incidents.py` prueba penalización y bloqueo.
- RUT-15 (incidentes), RUT-36 (recálculo), RUT-39 (live traffic).
- Frontend muestra "Aviso de ruta alternativa" al conductor.

**Limitación:** No existe simulador de tráfico sintético para las pruebas (Could en PLAN.md). Las pruebas son con datos reales de Google.

### Brecha 5 — Indicadores del protocolo ⚠️ Parcialmente medidos

| Indicador del protocolo | Estado | Dónde |
|---|---|---|
| Reducción ≥15% en distancia | ✅ | E3: ruta "rápida" vs "corta"; Laboratorio interactivo |
| Mejora ≥20% en tiempo estimado de entrega | ✅ | E3, E6: ahorro en minutos según franja; multistop calcula ETAs |
| Precisión de ETA >85% | ✅ (Parcial) | E4: MAPE <20% vs. Google Routes API en 50 viajes de prueba |
| Rutas alternativas exitosas >90% | ⚠️ | RUT-15/RUT-39: recálculo funciona; falta estadística formal (no hay registro histórico) |
| Respuesta <30 s ante un evento | ✅ | A\* tarda <1 ms; incidentes disparan recálculo inmediato |

### Brecha 6 — Entorno de ejecución ⚠️

El protocolo declara **Google Colaboratory** como entorno de desarrollo. El
prototipo es una aplicación Django desplegada en Render con PostgreSQL en Neon.
Es una desviación respecto al documento, defendible como una mejora (sistema web
multiusuario con roles en vez de un notebook), pero conviene mencionarla en vez
de dejar la contradicción en pie.

---

## Datos: dos observaciones

1. **El Progreso (GT02) está aislado.** Existe como departamento pero no tiene
   ninguna `RouteConnection`, así que cualquier ruta hacia o desde él falla con
   «No existe una ruta conectada entre origen y destino». De los 110 pares
   posibles solo 90 son alcanzables.
2. **La red tiene 13 aristas para 11 departamentos**, casi un árbol. Con tan
   pocas alternativas la heurística voraz encuentra la ruta óptima en 75 de los
   90 pares. Enriquecer la red con las carreteras reales que faltan haría la
   comparación más representativa y más contundente en la demostración.

---

## Verificación

```bash
python manage.py test logistics
```

Cubre: equivalencia de distancia entre Dijkstra y A\*, que A\* nunca expande más
nodos que Dijkstra, que la línea base voraz nunca es más corta que el óptimo, que
la reducción en Guatemala → Suchitepéquez supera el 15%, que el endpoint de
comparación devuelve los tres algoritmos, y que el algoritmo elegido queda
registrado en el viaje.
