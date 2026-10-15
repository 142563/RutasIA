# Rendimiento de mapas · RUT-94

## Problema observado (2026-10-14)

Julio reportó lentitud severa en los mapas de `enruta.world`. En Hoy se observaron
129 trazos de tráfico con 20,545 vértices. El SVG reconstruía sus coordenadas y cadenas
en cada movimiento de cámara; `OverlayView.draw` y `bounds_changed` pedían redibujar
por separado. El estado del tooltip también repetía trabajo de las capas pesadas.

## Corrección

- Los avisos de cámara comparten un `requestAnimationFrame`; se cancela al desmontar.
  Un `ResizeObserver` actualiza las capas al cambiar el tamaño del mapa.
- Las carreteras de tráfico se proyectan una vez a coordenadas mundiales de Google,
  relativas al centro de Guatemala. Arrastrar solo traslada el grupo SVG; el zoom usa
  el ancho mundial actual de `MapCanvasProjection` dividido entre 256 (equivalente
  a `2 ** zoom`). La preparación se reutiliza mientras no cambie la geometría,
  el perfil o el nivel de zoom.
- Douglas–Peucker simplifica **el dibujo**, con tolerancia de 0.75 píxeles al zoom
  actual; conserva los extremos y recupera detalle al acercar. No altera polilíneas
  almacenadas, pesos, rutas elegidas, tiempos ni tráfico.
- Se omiten los trazos cuya caja queda fuera del mapa, con margen de 8 píxeles.
  Un tramo que cruza la pantalla sigue incluido aunque sus extremos estén afuera.
- El tooltip reutiliza la capa personalizada y los puntos preparados de las rutas.
  La red base no se construye cuando una capa personalizada la reemplaza.

Se conservan los interruptores de tráfico, colores por congestión, nombres y sentidos,
marcadores, GPS, selección de ubicaciones y mapa esquemático. No se consulta la capa
visual de tráfico de Google ni se agregan solicitudes externas.

La conversión corresponde al mapa vial plano actual (sin rotación ni inclinación).
Si el mapa tiene rotación/inclinación, o aún no tiene una proyección mundial válida,
se usa el respaldo de proyección individual para conservar la alineación.
Referencia: [coordenadas de Maps JavaScript API](https://developers.google.com/maps/documentation/javascript/coordinates).

## Validación

- `npm ci`: 192 paquetes auditados, 0 vulnerabilidades informadas.
- `npx tsc -b`: correcto.
- `npx vitest run`: 133 pruebas, 30 archivos; 9 pruebas nuevas de dibujo y eventos.
- `npm run build`: correcto; continúa el aviso de bundle mayor de 500 kB.
- Backend: `DATABASE_URL= python manage.py test --noinput`, 388 pruebas correctas
  en 332.140 s, SQLite; claves de Google/Resend vacías y APIs externas simuladas.
- Chrome, prueba local del componente real con geometría **simulada**: 129 carreteras,
  20,545 puntos de entrada y 1,419 vértices dibujados en la vista inicial. Tras mover
  y ampliar, el contador de proyecciones mundiales permaneció en 20,545; la vista
  ampliada mostró 35 trazos y 509 vértices. No hubo nuevas proyecciones por cámara.
- Inspección visual de esa prueba en claro/oscuro y a 375 px, sin desborde horizontal.

Los números de la prueba simulada no son una medición de FPS ni de rendimiento en
producción. Tras integrar y autorizar el despliegue, comprobar Hoy, Pedidos,
Planificar, Rutas y Análisis con Google real: pan/zoom, cambio de tamaño, alineación
de carreteras y marcadores, selección de punto, tooltip y ambos interruptores.
Esta entrega no despliega ni cambia datos de producción.
