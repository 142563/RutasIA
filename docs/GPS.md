# GPS del vehículo (RUT-76)

El conductor puede pulsar **Autorizar y compartir ubicación** en su ruta en
curso, dentro de `/conductor`. Además del botón, el navegador solicita el permiso
de geolocalización. No se pide GPS al iniciar sesión ni se activa automáticamente.
El indicador cambia a **Compartiendo ubicación** después del primer envío
aceptado; un botón permite detenerlo.

El celular toma mediciones con `watchPosition` y envía la más reciente cada
12 segundos. No transmite mediciones de más de 30 segundos ni acumula envíos
sin conexión. Detiene watcher, temporizador y petición pendiente al salir de
esa pantalla, revocar el permiso o dejar de estar en curso. Al entrar a una
parada se detiene; al volver a la ruta debes autorizar nuevamente. No funciona
como tracker en segundo plano: el navegador puede suspender GPS y timers si
se bloquea el teléfono. Usa HTTPS o localhost.

## Recepción y privacidad

`POST /api/driver/position/` requiere sesión de conductor y CSRF. Recibe
`route_id`, `lat`, `lng` y, opcionalmente, `speed_kmh`, `heading`, `accuracy_m`.
Solo admite la ruta propia **en curso**. Nunca guarda posiciones antes de
iniciar ni después de completar o cancelar una ruta. Usa la hora del servidor
en `recorded_at`; el celular no puede alterar el límite enviando fechas.

- Latitud: −90…90; longitud: −180…180.
- Velocidad: 0…300 km/h; orientación: 0 ≤ grados < 360.
- Precisión: 0…100000 metros. Las tres últimas admiten `null`.
- Rechaza booleanos, cadenas, NaN e infinito.
- Esta sesión fija `source=phone`; intentar enviar `tracker` responde 400.
- Máximo una posición cada cinco segundos **por conductor**, incluso entre
  rutas distintas. Un UPDATE condicional de `Driver.last_position_at`, dentro
  de la misma transacción, reserva el intervalo compartido por los workers.
  También se comprueba el historial bajo ese bloqueo: una edición concurrente
  del conductor que restablezca el reloj no permite saltarse el intervalo.
  PostgreSQL también bloquea la ruta mientras se comprueba el estado. Las
  pruebas locales usan SQLite; no se hizo una prueba concurrente en PostgreSQL.

Respuestas: 201 aceptada, 400 inválida/ruta detenida, 404 ajena o inexistente,
403 rol incorrecto, 401 sin sesión, 429 intervalo demasiado corto. No registra
coordenadas en logs ni publica un endpoint anónimo.

`GET /api/v2/routes/<id>/positions/?since=ISO` exige admin o despachador. Devuelve
`latest` (puede ser `null`) y `positions` en orden temporal. La traza se limita
a los últimos 30 minutos y 360 posiciones. `since` debe incluir zona horaria,
se aplica solo a la traza y no amplía la ventana; `latest` conserva la hora real
de la última medición, aunque sea antigua. Las posiciones de otras rutas no
se incluyen.

Las mediciones se conservan asociadas a la ruta para el análisis posterior;
borrar la ruta o conductor elimina sus posiciones. No se implementó una
purga por antigüedad: antes del piloto hay que acordar la política de retención
y quién puede exportar datos de localización. Integrar también el aislamiento
de caché de sesión de RUT-67 antes de desplegar GPS.

## Mapa del despachador

Hoy y el detalle consultan cada diez segundos mientras la ruta siga en curso.
`NetworkMap.vehicles` es opcional: muestra el camión y una línea fina del
recorrido **observado**, independiente del camino planificado por A*.
El título accesible del marcador indica la hora del último GPS.
La interpolación dura 1.2 segundos entre mediciones, sin extrapolar; con
movimiento reducido pasa directamente a la medición recibida. Un mapa
sin Google conserva el marcador y la traza en su proyección esquemática.

## Tracker físico futuro (diseño, sin implementación)

Un dispositivo tendría credencial propia revocable, guardada como hash y
vinculada a un vehículo/conductor. Su autenticación resolvería esa asociación
en el servidor y verificaría una ruta activa; no aceptaría un `driver_id`
arbitrario del dispositivo. Usaría el mismo caso de uso de validación/límite
y asignaría `source=tracker` en el servidor. El token no reemplaza la sesión
ni permite leer las trazas. Hay que definir rotación, revocación y prevención
de repetición antes de habilitar ese canal. Esta tarjeta solo reserva el valor
`tracker` en el modelo, sin crear tokens ni autenticación de dispositivos.

## Integración local

Rama `codex/rut-76`, sin push ni merge. La migración `0014_vehicle_position`
parte de `0013_order_recipient_email`; Claude debe unir dependencias con
`0014_edge_geometry` de RUT-75 y otras migraciones paralelas. También revisar
las modificaciones paralelas a NetworkMap de RUT-75/RUT-77 y mantener sus
props opcionales al integrar. No se capturó ninguna ubicación real ni se
hicieron llamadas pagadas a Google.
La sección 15 de PLAN.md no existe en la base `origin/main` 696d02d de esta
rama; se leyeron las reglas disponibles y la sección 14. La integración debe
preservar cualquier documentación más reciente de Claude.

Verificación local (2026-10-11): suite final de Django con 249 pruebas
aprobadas en SQLite, incluyendo el historial que impide restablecer el límite.
Vitest: 78 pruebas en 19 archivos. `npm ci`, `npx tsc -b`, `npm run build` y
`makemigrations --check --dry-run` correctos. GPS simulado; no se hizo revisión
visual del marcador en un celular real de 375 px ni con Google. Se mantiene
el aviso de chunk de 513.84 kB y la alerta heredada de `source-map-js`
indicada en la revisión de dependencias.
