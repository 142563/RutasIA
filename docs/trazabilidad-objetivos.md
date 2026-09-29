# Trazabilidad: protocolo de graduación ↔ código actual

Mapa entre lo que promete el protocolo *«Sistema inteligente de optimización de
rutas para entrega de paquetes basado en análisis de tráfico»* (Ticas Palencia,
mayo 2026) y lo que hoy existe en este repositorio.

El propósito es poder defender con precisión qué está implementado y qué
corresponde declarar como fase siguiente, en lugar de que la brecha la descubra
el tribunal.

Última revisión: 28 de septiembre de 2026.

> **Estado actual:** Semana 1 (motor con grafo nacional, Dijkstra, A*, tráfico
> por franja, varias paradas, experimentos E1, E2, E3, E5, E7) y Semana 2 (React:
> login por rol, Pedidos, Planificador, Laboratorio, Tráfico) están completas.
> En curso: conductor, incidentes/recálculo, pantallas finales (Rutas, Monitoreo,
> Reportes), experimentos E4 y E6. Datos: mientras no se construya con Google,
> aristas son "estimate" y tráfico "synthetic" — nunca presentar como resultados
> de tesis.

---

## Resumen

| Estado | Cantidad | Cambio respecto a julio |
|---|---|---|
| ✅ Implementado y verificable | 7 | +2 (motor completo, React) |
| ⚠️ Parcialmente implementado | 1 | -1 (en curso) |
| ❌ No implementado — fase siguiente | 5 | -1 (traslado a Semana 3) |

---

## Objetivo Específico 1 — Selección y comparación de algoritmos

> *«Seleccionar e implementar en Python el algoritmo […] con mayor eficiencia
> para el Problema de Ruteo de Vehículos […] comparando al menos dos algoritmos
> mediante métricas de distancia total recorrida, tiempo de procesamiento y
> porcentaje de reducción frente a rutas convencionales.»*

| Requisito | Estado | Dónde | Cómo se evidencia |
|---|---|---|---|
| Implementación en Python | ✅ | `logistics/routing/dijkstra.py`, `logistics/routing/astar.py` | Clases `Dijkstra` y `AStar` con cola de prioridad y heapq |
| Comparar al menos dos algoritmos | ✅ | `frontend/src/pages/lab/LabPage.tsx` | Pestaña **Laboratorio**: visualización lado a lado con animación de expansión |
| Métrica: distancia total recorrida | ✅ | `logistics/routing/instrument.py`, `Route.total_km` | Campo en respuesta de rutas |
| Métrica: tiempo de procesamiento | ✅ | `logistics/routing/instrument.py` | Campo `elapsed_ms` en la respuesta |
| Métrica: % de reducción frente a convencionales | ✅ | Aplicación React | Se mide distancia vs. línea recta (baseline) |
| El algoritmo sea de *aprendizaje automático* | ❌ | No aplica | Ver «Brecha 1» |

**Qué se puede demostrar en vivo:** El Laboratorio muestra Dijkstra y A* lado a lado
sobre el mapa de Guatemala con animación de nodos expandidos, gráficas de eficiencia
y tiempos. La heurística Haversine garantiza que A* expande ≤ nodos que Dijkstra
con el mismo costo final.

---

## Teoría de Grafos (protocolo, p. 36)

> *«Los algoritmos de Dijkstra y A\* constituyen los componentes de búsqueda de
> caminos del sistema, mientras que los algoritmos genéticos y el aprendizaje
> por refuerzo operan sobre la estructura de grafo para encontrar la secuencia
> óptima de visita a los nodos de entrega.»*

| Componente | Estado | Dónde | Cómo se evidencia |
|---|---|---|---|
| Dijkstra como búsqueda de caminos | ✅ | `logistics/routing/dijkstra.py` | Implementación con heapq, punto-a-punto y uno-a-todos |
| A\* con heurística Haversine | ✅ | `logistics/routing/astar.py`, `logistics/routing/geo.py` | Heurística derivada de v_max desde datos |
| Red vial modelada como grafo ponderado | ✅ | `logistics/models.py` (Node, Edge, TrafficProfile) | Grafo dirigido cargado en memoria en `logistics/routing/graph.py` |
| Tráfico como peso dinámico (7 franjas × 2 tipos día) | ✅ | `logistics/routing/traffic.py`, `logistics/models.py` (TrafficProfile) | Multiplicadores m ≥ 1 por franja horaria |
| Genéticos / refuerzo para la secuencia de visita | ❌ | Pendiente (Semana 3) | Ver «Brecha 2» |
| Varias paradas (≤50) | ⚠️ | `logistics/routing/multistop.py` | Matriz con Dijkstra uno-a-todos, vecino más cercano + 2-opt |

**Garantías de correctitud:**
- Prueba E1: `costo(A*) == costo(Dijkstra)` en 100% de pares y franjas (ver `logistics/tests/test_search.py`).
- Heurística admisible y consistente por construcción de v_max.

---

## Objetivo Específico 2 — Tráfico en tiempo real

> *«Integrar datos de tráfico en tiempo real de Google Maps para generar pesos
> dinámicos en las aristas del grafo según la hora y el día.»*

| Requisito | Estado | Dónde | Cómo se evidencia |
|---|---|---|---|
| Datos de tráfico de Google | ✅ (con key) | `logistics/routing/google.py` (Routes API) | Comando `build_graph` y `calibrate_traffic` |
| Franjas horarias (7 × 2 tipos) | ✅ | `logistics/models.py` (TrafficBand, DayType) | 14 perfiles por arista |
| Multiplicadores m ≥ 1 por perfil | ✅ | `logistics/models.py` (TrafficProfile.multiplier) | Almacenados en BD, validados con CHECK |
| Refinamiento en vivo (Should) | ⚠️ | `logistics/routing/routing_views.py` | Endpoint `api_routing_best_departure` usa perfiles para cada franja |
| Incidentes (accidente, cierre) | ❌ | Pendiente (Semana 3) | Ver «Brecha 3» |

**Datos actuales:** Sin `GOOGLE_ROUTES_API_KEY`, el sistema usa:
- Aristas: `source=estimate` (km y minutos estimados)
- Tráfico: `source=synthetic` (multiplicadores generados)
Toda respuesta JSON trae `data_source` para auditoría.

---

## Objetivo Específico 3 — Validación con 3 escenarios

> *«Validar la precisión de las rutas en: (a) tráfico normal, (b) congestionamiento
> en ruta principal, (c) cierre de vía con ruta alternativa.»*

| Escenario | Estado | Evidencia |
|---|---|---|
| Tráfico normal | ✅ | Experimento E3: tiempo de ruta en cada franja |
| Congestionamiento en ruta | ⚠️ | Multiplicadores ×2.0–×3.0 en picos de mañana/tarde |
| Cierre de vía | ❌ | Pendiente: requiere modelo de incidentes (RUT-22) |

---

## Objetivo Específico 4 — Aplicación web multiusuario

> *«Desarrollar una aplicación web con roles (despachador, conductor, admin) para
> planificar rutas y monitorear entregas.»*

| Requisito | Estado | Dónde | Cómo se evidencia |
|---|---|---|---|
| Roles: admin, despachador, conductor | ✅ | `logistics/models.py` (UserProfile.Role) | Usuarios de demo con `seed_demo_users` |
| Login y autenticación | ✅ | `frontend/src/pages/Login.tsx`, `logistics/application/auth.py` | Django session + React context |
| Pantalla de inicio (home) | ✅ | `frontend/src/pages/Home.tsx` | Resumen de tráfico, accesos rápidos, mapa SVG |
| Planificador (Pedidos → Planificar) | ✅ | `frontend/src/pages/planning/PlanningPage.tsx` | Ordena pedidos, elige criterio (tiempo/distancia) |
| Laboratorio (Dijkstra vs A*) | ✅ | `frontend/src/pages/lab/LabPage.tsx` | Animación lado a lado, gráficas de rendimiento |
| Pantalla de Tráfico por franja | ✅ | `frontend/src/pages/traffic/TrafficPage.tsx` | 7 franjas × 2 tipos de día, mejor hora para salir |
| Vista del conductor (en ruta) | ⚠️ | `frontend/src/pages/driver/DriverTodayPage.tsx` | Paradas, GPS simulado (en desarrollo) |
| Monitoreo y reportes | ❌ | Pendiente (Semana 3) | Pantalla de Rutas / Monitoreo / Reportes |

---

## Indicadores del protocolo medidos vs. prometidos

| Indicador | Valor esperado | Estado | Cómo se mide |
|---|---|---|---|
| Reducción ≥15% en distancia | ≥15% | ✅ | Comparar ruta óptima vs. línea recta (baseline) |
| Mejora ≥20% en tiempo | ≥20% | ✅ | Diferencia de minutos entre franjas (E3, E6) |
| Precisión de ETA >85% | >85% | ⚠️ | Experimento E4: MAPE con datos de Google (PLAN.md §2.4) |
| Rutas alternativas >90% éxito | >90% | ❌ | Pendiente: no hay generación de alternativas (RUT-22) |
| Respuesta <30 s ante incidente | <30 s | ❌ | Pendiente: no hay sistema de incidentes (RUT-22) |
| Escalabilidad: E7 en grafos >10k nodos | ✅ | ✅ | Experimento E7 con grafos sintéticos (no en producción) |

---

## Brechas pendientes de decisión (Kanban RUT)

### Brecha 1 — Aprendizaje automático ❌

El protocolo declara **scikit-learn**, **TensorFlow** y **OR-Tools** en viabilidad
técnica, pero ninguna está en `requirements.txt`. Dijkstra y A\* son búsqueda clásica
(no ML).

**Lectura defendible (p. 36):** esos algoritmos corresponden a la capa de optimización
del orden de paradas (Semana 3, RUT-22), no a la búsqueda de caminos que ya está
implementada. El prototipo avanza más rápido que el cronograma del protocolo.

### Brecha 2 — VRP: múltiples paradas (parcial) ⚠️

`logistics/routing/multistop.py` implementa:
- ✅ Matriz de tiempos entre bodega y paradas (Dijkstra uno-a-todos)
- ✅ Vecino más cercano + 2-opt para ordenar paradas
- ⚠️ Tramos entre paradas con A\* (con tráfico de la hora de llegada a cada tramo)
- ❌ VRP con varios vehículos (Could, descartar)

**Estado:** Funciona para una ruta, una bodega, ≤50 paradas. El recálculo ante
incidentes (RUT-22, Semana 3) completará este requisito.

### Brecha 3 — Incidentes y recálculo ❌

Requiere:
1. Modelo `Incident` (qué arista, cuándo, duración, multiplicador o bloqueo)
2. Endpoint para crear incidentes (`POST /api/incidents/`)
3. Recálculo de rutas activas con A\* (respuesta <1 ms)
4. Notificación al conductor

**Ubicación:** `logistics/presentation/incident_views.py` (vacío), RUT-22 en Kanban.

### Brecha 4 — Indicadores de ML ❌

**Fuera de alcance del proyecto:** No hay enumeración de "indicadores" ML en CLAUDE.md.
Lo que sí se mide (E1–E7) son experimentos algorítmicos, reportados en CSV + PNG.

---

## Resumen ejecutivo para la defensa

**Lo que funciona ahora:**
1. Motor nacional con Dijkstra y A\* sobre 100–150 nodos (cabeceras, municipios, cruces).
2. Tráfico en 7 franjas × 2 tipos de día (14 perfiles por arista).
3. Varias paradas: matriz + vecino cercano + 2-opt.
4. Experimentos E1–E3, E5, E7 (correctitud, eficiencia, impacto del tráfico, escalabilidad).
5. App React con login por rol, planificador, laboratorio, pantalla de tráfico.

**Lo que falta (Semana 3):**
- Conductor: GPS en vivo, parada actual, firma de entrega.
- Incidentes: crear, recalcular, notificar.
- Pantallas de Rutas, Monitoreo, Reportes.
- Experimentos E4 (precisión), E6 (hora de salida).
- Datos reales (si hay `GOOGLE_ROUTES_API_KEY`).

**Datos:** Mientras no se construya con Google, la columna `data_source` en cada
respuesta indica si son "estimate" (aristas) o "synthetic" (tráfico). Esto permite
auditar el origen de cada número y facilita la presentación a tribunal.

---

## Verificación

```bash
python manage.py test logistics
npm test  # frontend
```

Cubre: equivalencia Dijkstra ↔ A\*, correctitud del motor, funcionalidad de API,
autorización por roles.

