# Prototipo de diseño (referencia)

Pantallas del prototipo navegable, en estilo minimalista. Son la **referencia visual** para construir el frontend en React.

- Lienzo interactivo (con botón Play): https://claude.ai/artifact/EsmmFBakudic3pUQBT5GrK

| Archivo | Pantalla |
|---------|----------|
| `Main.dc.html` | Despachador · Planificador (más corta vs más rápida con tráfico) |
| `Pedidos.dc.html` | Despachador · Pedidos + panel "Nuevo pedido" |
| `Conductor-Hoy.dc.html` | Conductor · Mi ruta de hoy |
| `Conductor-Parada.dc.html` | Conductor · Detalle de parada |

> Estos archivos usan el formato del lienzo (`<x-dc>`, `{{...}}`, `<sc-if>`, `<sc-for>`). **No se abren directamente en el navegador**: sirven para leer la estructura, los estilos (colores, tamaños, espaciados) y los textos al traducirlos a componentes de React.

Pendiente de diseñar (ver `docs/PLAN.md` §7):
- El Planificador sobre el mapa de Guatemala (hoy muestra una ciudad de ejemplo).
- Laboratorio Dijkstra vs A\*.
- Mapa de tráfico por franja horaria.
- Aviso de ruta alternativa para el conductor.

Todos los datos del prototipo son de ejemplo.
