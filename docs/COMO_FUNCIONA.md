# Cómo funciona (explicado simple)

## La idea en una frase

Le das al sistema **los paquetes que hay que entregar** y **a qué hora sale el camión**. El sistema te dice **en qué orden visitar las entregas y por qué carreteras ir** para tardar lo menos posible **con el tráfico de esa hora**.

## Cómo se usa (3 pasos)

1. **Pedidos:** registras cada paquete con su dirección. Aparece como un punto en el mapa.
2. **Planificar:** eliges los pedidos y la hora de salida. El sistema calcula la ruta y te muestra:
   - el tiempo total de manejo y la hora de regreso;
   - la comparación **"Más rápida" (con tráfico) vs "Más corta" (en km)**;
   - si te conviene salir a otra hora ("si sales a las 15:30 ahorras 25 min").
3. **Asignar:** confirmas con un conductor y un vehículo. El conductor entra con su usuario en el celular, ve sus paradas en orden y marca cada entrega. Tú ves el avance en **Monitoreo**.

Extras para la tesis:
- **Laboratorio:** Dijkstra y A\* lado a lado sobre el mapa, contando cuántos nodos explora cada uno.
- **Tráfico:** qué tramos se ponen lentos en cada franja del día.
- **Reportes:** resultados de los experimentos.

## Qué pasa por dentro

```
   Google Maps                       Nuestro motor (el aporte de la tesis)
 ┌─────────────────┐               ┌──────────────────────────────────────┐
 │ Duración de cada│  (una vez,    │ Grafo de Guatemala: 108 lugares y     │
 │ tramo con y sin │   por lotes)  │ 260 tramos. Cada tramo cuesta MINUTOS │
 │ tráfico         │ ────────────► │ = minutos sin tráfico × multiplicador │
 └─────────────────┘               │   de la franja horaria (≥ 1)          │
                                   │                                      │
 ┌─────────────────┐               │ 1. Dijkstra: tiempos entre todas las │
 │ Mapa de fondo y │ ◄──────────── │    paradas (una "tabla de tiempos")  │
 │ dibujo de la    │  (solo para   │ 2. Vecino más cercano + 2-opt: el    │
 │ carretera real  │   mostrar)    │    ORDEN de las paradas              │
 └─────────────────┘               │ 3. A*: el CAMINO de cada tramo       │
                                   └──────────────────────────────────────┘
```

- **El grafo:** cada **nodo** es un lugar (las 22 cabeceras, municipios importantes y cruces de carretera como Los Encuentros o El Rancho). Cada **tramo** es un pedazo de carretera entre dos nodos.
- **El tráfico:** el día se divide en 7 franjas (madrugada, pico de la mañana, media mañana, mediodía, tarde, pico de la tarde y noche). Cada tramo tiene un **multiplicador** por franja. Por ejemplo, ×1.8 en el pico de la mañana significa que tarda 80 % más que sin tráfico.
- **Dijkstra** revisa los caminos empezando por los más cortos en tiempo hasta llegar al destino. Siempre encuentra el mejor, pero revisa mucho.
- **A\*** hace lo mismo, pero "apunta" hacia el destino. Usa la distancia en línea recta dividida entre la velocidad más alta posible del grafo, así que **nunca se pasa** en su estimación. Por eso encuentra **la misma ruta que Dijkstra revisando menos nodos**, y eso se demuestra con pruebas automáticas.
- **Google** solo pone los datos de tráfico y el dibujo. **La decisión de qué ruta tomar la hace nuestro algoritmo.**

## ¿Por qué a veces dice "datos estimados" o "sintéticos"?

Para probar sin gastar en Google, `python manage.py preparar` crea tramos **estimados** y tráfico **sintético**. Sirven para ver que todo funciona, pero **no son resultados para la tesis**. Con la key de servidor (`GOOGLE_ROUTES_API_KEY`) corres `python manage.py preparar --google` y quedan datos reales.

## ¿Y el mapa?

- **Con `GOOGLE_MAPS_API_KEY` en `.env`:** ves Google Maps de fondo, con zoom y arrastre. La ruta elegida se dibuja **por la carretera real** siguiendo los lugares que eligió el algoritmo.
- **Sin la key, o si Google la rechaza:** ves un mapa esquemático (puntos y líneas) y abajo un aviso que explica por qué.
- **Si la ves pero Google la rechaza**, las causas típicas son tres: la key no permite `http://127.0.0.1:8000/*` en *HTTP referrers*, falta activar **Maps JavaScript API** o **Directions API**, o el proyecto no tiene facturación. Paso a paso en [`GOOGLE_KEYS.md`](GOOGLE_KEYS.md).
