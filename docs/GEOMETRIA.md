# Geometría del grafo (RUT-75)

Cada `Edge.polyline` representa su **sentido dirigido**. `RouteSample.polyline`
conserva la respuesta codificada para reutilizarla. Los pesos, minutos y
algoritmos no consultan esta geometría: Dijkstra y A* siguen trabajando en memoria.

Después de migrar, un operador con la key del servidor puede ejecutar:

```sh
python manage.py build_graph --polylines-only
```

Rellena únicamente aristas activas cuya polilínea está vacía. No modifica sus
distancias, minutos, fuentes, clases ni estado. Primero usa la muestra sin
tráfico guardada; si no tiene geometría, pide `computeRoutes` con
`TRAFFIC_UNAWARE`, `HIGH_QUALITY` y `routes.polyline.encodedPolyline`.
La construcción normal con Google también completa las geometrías activas.

**Costo del relleno:** una llamada por arista dirigida faltante que tampoco
tenga polilínea en caché; cero para las completas o disponibles en caché. El
comando imprime el número de solicitudes realizadas y los tramos sin respuesta.
La semilla actual tiene 260 pares dirigidos: si todos están activos, faltantes
y sin caché, son 260 llamadas; con el relleno completo, la repetición hace cero.
Una respuesta fallida o sin polilínea queda pendiente para el siguiente intento.
No se hicieron llamadas reales ni se consumió cuota durante el desarrollo.

Para conocer la cantidad pendiente sin llamar a Google:

```python
from logistics.models import Edge, RouteSample
cached = set(RouteSample.objects.filter(band="", day_type="").exclude(
    polyline="").values_list("origin_id", "destination_id"))
pending = Edge.objects.filter(is_active=True, polyline="").values_list(
    "origin_id", "destination_id")
print(sum(pair not in cached for pair in pending))
```

`GET /api/routing/geometry/?edges=[["origen","destino"]]` exige sesión y
acepta hasta 500 pares, serializados en JSON y codificados como parámetro URL.
Devuelve solo las aristas activas encontradas, incluyendo polilíneas vacías.
No llama a Google. El mapa consulta lotes de 25 para limitar la longitud de URL.

El decodificador propio concatena las aristas en el orden elegido por el motor,
sin invertirlas ni submuestrearlas; elimina solo extremos compartidos iguales.
Si una falta, está vacía o mal codificada, conserva Directions como respaldo
sobre Google; sin Google usa el esquema existente. Una ruta completa también
se dibuja con geometría real sobre el mapa esquemático.

El trazo guardado evita que Directions vuelva a elegir un camino distinto.
Si un nodo del grafo sigue ubicado dentro de un municipio, la geometría que
Google midió para esa arista puede conservar ese acceso: corregir coordenadas
de nodos requiere una revisión independiente del grafo. No se declara una
validación visual nacional ni resultados de tesis sin datos reales.

Integración local: rama `codex/rut-75`, sin push ni merge. La migración
`0014_edge_geometry` parte de `0013_order_recipient_email`; Claude debe revisar
dependencias si integra otra migración paralela antes de esta.

Verificación local (2026-10-11): 246 pruebas de Django aprobadas en SQLite,
74 pruebas de Vitest en 18 archivos, `npm ci`, `npx tsc -b` y `npm run build`
correctos; `makemigrations --check --dry-run` sin cambios pendientes.
Google estuvo simulado. El build conserva el aviso de chunk mayor a 500 kB.
`npm audit` detectó una alerta alta heredada en `source-map-js`
(GHSA-68fv-2mgg-jv7q); su actualización queda para la revisión de dependencias.
