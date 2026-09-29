# Keys de Google: paso a paso

El proyecto usa **dos keys distintas**. Nunca las subas a git: van en `.env` (local) y en las variables de entorno de Render.

| Variable | Tipo | Para qué | ¿Bloquea la tesis? |
|---|---|---|---|
| `GOOGLE_ROUTES_API_KEY` | Servidor | `build_graph` y `calibrate_traffic`: km, t0 y tráfico reales | **Sí**: sin ella los datos son estimados/sintéticos |
| `GOOGLE_MAPS_API_KEY` | Navegador | Places (autocompletar direcciones) y Directions (dibujo real) | No: la app usa el mapa esquemático propio |

## 1. Proyecto y facturación

1. Entra a <https://console.cloud.google.com/> con tu cuenta y crea un proyecto, por ejemplo `rutasia-tesis`.
2. Menú **Facturación**: vincula una cuenta de facturación al proyecto. Google la pide aunque el uso sea bajo.
3. **Facturación → Presupuestos y alertas → Crear presupuesto**: pon un monto pequeño (por ejemplo USD 20) con alertas al 50 %, 90 % y 100 %. Así ningún error de código te genera un cobro inesperado.

## 2. Activar las APIs

En **APIs y servicios → Biblioteca**, activa:

- **Routes API**, para la key del servidor.
- **Maps JavaScript API**, **Places API (New)** y **Directions API**, para la key del navegador (solo si vas a usar Places y Directions).

## 3. Key del servidor (`GOOGLE_ROUTES_API_KEY`)

1. **APIs y servicios → Credenciales → Crear credenciales → Clave de API**.
2. Edítala. En **Restricciones de API** elige "Restringir clave" → solo **Routes API**.
3. En restricciones de aplicación puedes dejar "Ninguna" (se usa desde tu compu y desde Render). No la pongas nunca en el frontend.
4. Cópiala en `.env`, sin comillas ni espacios:
   ```
   GOOGLE_ROUTES_API_KEY=AIza...
   ```
5. Verifícala. Hace **una** consulta de un solo elemento:
   ```powershell
   python manage.py check_google
   ```

## 4. Key del navegador (`GOOGLE_MAPS_API_KEY`)

1. Crea otra **Clave de API**.
2. **Restricciones de aplicación → Sitios web (HTTP referrers)** y agrega:
   - `http://localhost:5173/*`
   - `http://127.0.0.1:8000/*`
   - `https://TU-SERVICIO.onrender.com/*`
3. **Restricciones de API**: Maps JavaScript API, Places API (New) y Directions API.
4. Guárdala en `.env` como `GOOGLE_MAPS_API_KEY=...`. Opcional: crea un **Map ID** con estilo desaturado y ponlo en `GOOGLE_MAPS_MAP_ID`.

## 5. Datos reales para la tesis

Cuando `check_google` diga OK:

```powershell
python manage.py build_graph          # ~260 elementos: km y t0 de cada tramo, más verificación
python manage.py calibrate_traffic    # ~3,640 elementos: 14 perfiles; pide confirmación antes de gastar
python manage.py run_experiments      # E1–E7 con datos reales (data_source=google en los CSV)
```

- Las respuestas quedan en `RouteSample`: repetir un comando en menos de 7 días **no vuelve a gastar**.
- `build_graph` imprime los tramos sin ruta, los rodeos y los tramos redundantes. Revisa esa lista junto con las coordenadas marcadas † en `logistics/routing/seed_data.py`.
- Antes de correr `calibrate_traffic`, revisa el precio vigente de *Compute Route Matrix* con tráfico en la página de precios de Google Maps Platform. El comando muestra cuántos elementos va a consultar.

## 6. En Render (cuando se haga el deploy)

En **Environment** agrega `GOOGLE_ROUTES_API_KEY` y `GOOGLE_MAPS_API_KEY` (ya están declaradas en `render.yaml` con `sync: false`).
