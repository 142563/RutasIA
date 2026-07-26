# Trazabilidad: protocolo de graduación ↔ código del prototipo

Mapa entre lo que promete el protocolo *«Sistema inteligente de optimización de
rutas para entrega de paquetes basado en análisis de tráfico»* (Ticas Palencia,
mayo 2026) y lo que hoy existe en este repositorio.

El propósito es poder defender con precisión qué está implementado y qué
corresponde declarar como fase siguiente, en lugar de que la brecha la descubra
el tribunal.

Última revisión: 25 de julio de 2026.

---

## Resumen

| Estado | Cantidad |
|---|---|
| ✅ Implementado y verificable en la aplicación | 5 |
| ⚠️ Implementado parcialmente | 2 |
| ❌ No implementado — fase siguiente | 6 |

---

## Objetivo Específico 1 — Selección y comparación de algoritmos

> *«Seleccionar e implementar en Python el algoritmo […] con mayor eficiencia
> para el Problema de Ruteo de Vehículos […] comparando al menos dos algoritmos
> mediante métricas de distancia total recorrida, tiempo de procesamiento y
> porcentaje de reducción frente a rutas convencionales.»*

| Requisito | Estado | Dónde |
|---|---|---|
| Implementación en Python | ✅ | `logistics/domain/services.py` |
| Comparar al menos dos algoritmos | ✅ | Pestaña **Laboratorio**; `POST /api/routes/compare/` compara tres |
| Métrica: distancia total recorrida | ✅ | `SearchResult.distance` |
| Métrica: tiempo de procesamiento | ✅ | `SearchResult.elapsed_ms`, mediana de 7 corridas con caché precalentada |
| Métrica: % de reducción frente a rutas convencionales | ✅ | `GreedyOptimizer` como línea base; `reduction_pct` en el endpoint |
| El algoritmo sea de *aprendizaje automático* | ❌ | Ver «Brecha 1» |

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
| Dijkstra como búsqueda de caminos | ✅ | `RouteOptimizer` |
| A\* con heurística Haversine | ✅ | `AStarOptimizer`, `haversine_km()` |
| Red vial modelada como grafo ponderado | ✅ | `RouteConnection`, `_build_graph()` |
| Genéticos / refuerzo para la secuencia de visita | ❌ | Ver «Brecha 1» |
| Pesos dinámicos según tráfico real | ❌ | Ver «Brecha 2» |

La heurística es admisible (nunca sobreestima el costo por carretera), lo que
garantiza que A\* conserve la optimalidad. Hay un test que lo comprueba sobre
todos los pares: `AlgorithmComparisonTests.test_astar_never_explores_more_nodes_than_dijkstra`.

---

## Brechas

### Brecha 1 — Aprendizaje automático ❌

El protocolo declara en la Tabla 1 de viabilidad técnica **scikit-learn**,
**TensorFlow** y **OR-Tools**, y el Objetivo General habla de *«algoritmos de
aprendizaje automático»*. Ninguna de las tres bibliotecas está en
`requirements.txt`, y Dijkstra y A\* son **búsqueda clásica en grafos, no
aprendizaje automático**: no hay entrenamiento, ni datos de ajuste, ni política
aprendida.

Es la discrepancia más visible entre el documento y el código, y conviene
plantearla antes de que la plantee el tribunal. Dos lecturas defendibles:

1. La página 36 asigna a Dijkstra y A\* el rol de capa de búsqueda de caminos, y
   esa capa **sí** está implementada y medida. Lo que falta es la capa superior
   (secuencia de visitas), que es donde entrarían los genéticos y el refuerzo.
2. El cronograma sitúa la validación en las semanas 13–16 y las conclusiones
   condicionan la verificación de la hipótesis a *«la fase de implementación y
   prueba»*. El prototipo actual va por delante de lo exigido para el protocolo.

### Brecha 2 — Tráfico en tiempo real como peso dinámico ❌

El protocolo pide que los pesos de los arcos *«varíen en función de las
condiciones de tráfico en tiempo real»*. Hoy:

- `logistics/domain/services.py` usa `RouteConnection.distance_km`, un valor
  fijo en la base de datos.
- `new google.maps.TrafficLayer()` (`static/logistics/app.js:763`) es una **capa
  visual**: pinta la congestión pero no alimenta ningún cálculo.
- `DirectionsService.route()` se invoca sin `drivingOptions.departureTime`, así
  que la respuesta no incluye `duration_in_traffic`.

Camino más corto para cerrarla: pedir `departureTime` a Directions y almacenar
`duration_in_traffic` como peso alternativo del arco, para poder optimizar por
tiempo además de por distancia.

### Brecha 3 — 50 puntos de entrega por ruta ❌

El alcance declara *«hasta 50 puntos de entrega simultáneos por ruta»*. El
prototipo resuelve **un solo par origen–destino**: `_validate_orders()`
(`logistics/application/services.py:29`) rechaza el viaje si los pedidos no
comparten el mismo origen **y** el mismo destino.

Mientras esa restricción exista no se está resolviendo el Problema de Ruteo de
Vehículos, sino el de camino más corto entre dos nodos. Levantarla es el
prerrequisito de la Brecha 1: sin múltiples paradas no hay secuencia de visitas
que optimizar.

### Brecha 4 — Tres escenarios de prueba ❌

El Objetivo Específico 3 exige validar en tráfico normal, congestionamiento en
ruta principal y cierre de vía con ruta alternativa. No existe ningún mecanismo
para simular congestión o cerrar un tramo: `RouteConnection` no tiene campo de
estado ni penalización temporal.

### Brecha 5 — Indicadores no medidos ❌

| Indicador del protocolo | Estado |
|---|---|
| Reducción ≥15% en distancia | ✅ medible hoy en el Laboratorio |
| Mejora ≥20% en tiempo estimado de entrega | ❌ el sistema no estima duración, solo distancia |
| Precisión de ETA >85% | ❌ no hay ETA ni valores reales contra los que comparar |
| Rutas alternativas exitosas >90% | ❌ no existe generación de rutas alternativas |
| Respuesta <30 s ante un evento | ⚠️ la búsqueda tarda <1 ms, pero no hay eventos que disparen recálculo |

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
