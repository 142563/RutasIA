# Seguridad de enruta: revisión del 10 de octubre de 2026

Esta revisión cubre el código del repositorio, pruebas locales con SQLite y una
consulta pública a `/api/config/` de enruta.world. No es una certificación ni una
prueba de penetración. No se accedió a la base de producción ni a los paneles de
Render, Neon, Google, Resend o Spaceship. No se copiaron secretos.

## Correcciones preparadas para revisión

Cada tarjeta se entrega en su propia rama desde `main`; aún necesita revisión e
integración por Opus. Un cambio subido a una rama no está desplegado.

| Tarjeta | Hallazgo | Cambio preparado |
| --- | --- | --- |
| RUT-64 | El acceso demo solo comprobaba el nombre de la cuenta. Si se promovía, podía conceder permisos adicionales sin contraseña. | Exigir el rol original y rechazar cuentas staff/superuser. Validar que el cuerpo JSON sea un objeto para responder 400 en lugar de 500. |
| RUT-65 | Con `DEBUG=False`, la aplicación podía usar la clave pública de desarrollo. No activaba HTTPS/HSTS en Django. | Exigir una clave privada de al menos 50 caracteres; redirigir a HTTPS y empezar con HSTS de una hora. Sin subdominios ni preload. |
| RUT-66 | `requirements.txt` fija Django 6.0.4, con avisos de seguridad posteriores. | Actualización dentro de la misma serie a 6.0.9 y pruebas completas antes de entregar. |
| RUT-67 | Al expirar o cambiar de sesión, las consultas anteriores podían seguir en la caché del navegador. | Vaciar la caché de consultas y mutaciones en los cambios de sesión, con pruebas de respuestas pendientes. |

La longitud de una clave no garantiza su aleatoriedad: genera una con Django y
guárdala únicamente en las variables privadas de Render. No uses una clave de
ejemplo ni la de otro entorno. Cambiarla puede cerrar sesiones existentes.

HSTS indica al navegador que use HTTPS durante ese plazo. Se mantiene una hora
para comprobar primero el dominio y el proxy; no se aumenta a un año ni se
extiende a subdominios sin verificar sus certificados. La cabecera del proxy
`X-Forwarded-Proto` debe llegar correctamente para evitar redirecciones en bucle.

Con RUT-65, la comprobación simulada dejó de reportar W004/W008. Conserva W005
(subdominios) y W021 (preload) porque se mantienen desactivados deliberadamente;
no se ocultaron las advertencias. Esto no equivale a una comprobación del panel
real ni del despliegue futuro.

## Evidencia y límites

- La respuesta pública de `/api/config/` tenía `demo_login=false`,
  `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY` y
  `Referrer-Policy: same-origin`. No incluía HSTS ni CSP en ese momento.
- En una configuración de producción simulada, sin conexión a Neon,
  `check --deploy` reportaba W004 (HSTS) y W008 (redirección HTTPS). Render también
  redirige HTTP en dominios propios; la advertencia de Django por sí sola no
  demuestra que producción aceptara credenciales por HTTP.
- CSRF está habilitado; las pruebas de sesión usan comprobaciones reales de
  CSRF. Las APIs de configuración y operaciones verifican roles en backend.
  Las pruebas de conductor verifican que no pueda modificar rutas ajenas.
- Solo `.env.example` está versionado; `.env` no está en la entrega. Esto no
  constituye una auditoría completa del historial Git ni de claves anteriores.
- `npm audit --omit=dev` reportó **0 avisos conocidos** en las dependencias de
  producción del frontend. No demuestra ausencia de vulnerabilidades.
- La consulta OSV de las seis dependencias directas de `requirements.txt`
  encontró avisos para Django 6.0.4 y ninguno para las otras cinco. OSV registra
  algunos CVE tanto como GHSA como PYSEC: no se sumaron como fallas distintas.
  Una consulta separada a Django 6.0.9 no devolvió avisos. Faltan dependencias
  transitivas, imagen de Render y componentes del sistema operativo.
- No se probó la explotación de los avisos. La aplicabilidad depende de qué
  funciones se usan; por ejemplo, el proyecto no instala middleware de caché
  global ni usa GeoDjango.

## Prioridades que siguen abiertas

| Prioridad | Tema | Trabajo y criterio de cierre |
| --- | --- | --- |
| Alta | Intentos de inicio de sesión | Limitar por cuenta y origen con un almacén compartido entre los tres workers. Probar 429, vencimiento, concurrencia y el login de `/accounts/` además de la API. No basta una caché local por proceso. |
| Alta | Contraseñas de Configuración | `_check_password` solo exige 10 caracteres; `create_user` no ejecuta por sí solo los validadores de Django. Aplicar `validate_password` al crear/cambiar contraseñas y probar contraseñas comunes, numéricas y similares al usuario. |
| Alta | Separar bases (RUT-38) | Entornos distintos en Neon, credenciales distintas y permisos mínimos; impedir que pruebas y datos demo alcancen producción. Verificarlo en los paneles sin publicar la URL privada. |
| Alta | Backups y recuperación | Confirmar retención y respaldo de Neon, probar una restauración en un entorno aislado y documentar cuánto dato/tiempo se puede perder. Un backup sin prueba de restauración no cierra este riesgo. |
| Alta | Cuentas de proveedores | Revisar 2FA, integrantes y permisos en GitHub, Render, Neon, Google, Resend y Spaceship. Rotar claves solo cuando exista evidencia de exposición o corresponda al procedimiento acordado. |
| Media | Política CSP (RUT-87) | Preparada en modo reporte: cabecera en HTML y API, hash SHA-256 del tema servido y receptor anónimo limitado a 16 KB. No bloquea ataques ni prueba compatibilidad de Maps en vivo. Revisar reportes y validar con la clave restringida antes de enforcement. |
| Media | Permisos de APIs del motor | Los endpoints de ruteo requieren sesión, pero no todos restringen el rol. Decidir cuáles necesita el conductor y probar que los restantes queden limitados a despacho/administración. `optimize` ya limita a 50 paradas. |
| Media | Costos y abuso de Google/Resend | Restringir la key del navegador por dominio y APIs; la key del servidor no debe llegar al frontend. Configurar cuotas, presupuestos y alertas. La caché de comprobación de tráfico es local por proceso: revisar concurrencia y almacén compartido. |
| Media | Datos personales y logs | Definir retención de nombres, teléfonos, direcciones, correos y firmas impresas. Los logs de notificaciones pueden incluir destinatarios y asuntos: reducirlos o limitar su acceso/retención. |
| Media | Monitoreo operativo | Alertas ante errores 500, fallos de correo, cron de tráfico y expiración de certificados. Verificar copias de seguridad y cron con evidencia periódica. |

RUT-55 aún figura En curso: faltan verificación de Resend, configuración privada
de su API key en Render y prueba de correo de punta a punta. RUT-63 exige esperar
a que RUT-55 esté Hecho. La key debe introducirla Julio directamente en el panel;
no debe pegarse en el chat ni en Git.

Para la tesis, también siguen pendientes la precisión E4 (RUT-43), validación de
coordenadas/tramos (RUT-20) y cierre de experimentos (RUT-17). Una interfaz pulida
no demuestra precisión del modelo; los datos sintéticos deben seguir señalados.

## Comprobaciones antes de integrar y desplegar

1. Opus revisa las ramas y ejecuta la suite completa después de combinarlas;
   `App.tsx` cambia en más de una tarjeta y necesita revisión conjunta.
2. Ejecutar pruebas de Django con `DATABASE_URL` explícitamente vacío. En
   PowerShell, una forma que también impide que `.env` lo reponga es:

   ```powershell
   .venv\Scripts\python.exe -c 'import os,runpy,sys; os.environ["DATABASE_URL"]=""; sys.argv=["manage.py","test","--noinput"]; runpy.run_path("manage.py",run_name="__main__")'
   ```

3. En `frontend/`: `npm ci`, `npx tsc -b`, `npx vitest run`, `npm run build`.
4. Verificar `DEBUG=False`, clave privada, hosts/orígenes exactos, cookies seguras,
   proxy HTTPS y cabeceras. `check --deploy` se debe ejecutar con la configuración
   real de producción; no copiar el archivo `.env` al repositorio.
5. Tras el deploy autorizado, comprobar login con CSRF, permisos, mapa y entrega.
   Confirmar en Resend y en la bandeja el correo de una prueba acordada.

## CSP en modo reporte (RUT-87, 11 de octubre de 2026)

`rutasia/csp.py` agrega `Content-Security-Policy-Report-Only` antes de los demás
middlewares: también cubre 401, 404, 405 y errores. No se agrega todavía
`Content-Security-Policy`. El hash del tema se calcula desde
`frontend/dist/app/index.html`, con la misma lectura y normalización de saltos de
línea que la vista `spa`; se actualiza al cambiar el build. Si no hay build no se
permite ningún script inline por hash. No se usa el hash de `frontend/index.html`
porque el contenido servido puede diferir tras compilar.

La política permite recursos locales y las familias de dominios de Maps de la
[guía oficial de Google](https://developers.google.com/maps/documentation/javascript/content-security-policy).
Las fuentes de la aplicación siguen siendo locales; se permiten fuentes de
Google para Maps. `data:`/`blob:` se limitan a las directivas correspondientes.
Los estilos inline se permiten para React y Maps; los scripts inline solo tienen
el hash del tema. `unsafe-eval` se conserva siguiendo el ejemplo de Google:
esta es una política de allowlist de observación, no una CSP estricta con nonces.
Revisar su necesidad y los dominios permitidos antes de hacerla obligatoria.

`POST /api/csp-report/` acepta el JSON clásico `csp-report` y lotes de la Reporting
API (hasta 16 reportes). No exige sesión ni CSRF porque el navegador envía estos
reportes automáticamente; esa excepción solo aplica a este endpoint. Rechaza
cuerpos mayores de 16 KB con 413, JSON inválido con 400 y tipos no compatibles
con 415. Lee como máximo 16 KB más un byte, sin cargar un cuerpo ilimitado.

El log `logistics.presentation.csp_views` conserva solamente directivas de una
lista cerrada y la cantidad recibida. Las directivas desconocidas se reducen a
`unknown`. Nunca registra el cuerpo, documento, recurso bloqueado, referrer,
dirección IP, fragmento de script, usuario ni URL con claves/tokens. Esto limita
el diagnóstico remoto: el origen concreto se debe investigar en la consola de
una prueba autorizada. Un reporte anónimo puede ser falsificado; no demuestra
un ataque. El límite por petición no limita el número de solicitudes: revisar
cuotas y retención de logs en el proveedor si aparece abuso.

### Antes de volverla obligatoria

1. Integrar y probar localmente con el build servido por Django, no solo con Vite
   (Vite no recibe la cabecera de este middleware). Repetir tras cambios en el
   script del tema, dependencias o versión semanal de Maps.
2. Con una clave de navegador restringida al entorno de prueba, revisar login,
   Hoy, pedidos/Places, Planificar, detalle y conductor en claro/oscuro y celular.
   Verificar mapas, geometrías/Directions, fuentes y consola sin violaciones.
   Sin clave solo se valida el mapa esquemático; no confirma Google Maps.
3. Revisar los conteos y directivas de los logs. No ampliar permisos por reportes
   anónimos sin reproducir primero el caso. No habilitar `report-sample` ni
   registrar cuerpos completos para investigar problemas.
4. Preparar un cambio separado que use `Content-Security-Policy` en lugar de la
   cabecera de reporte, con pruebas de regresión. Considerar nonces para el CSP
   estricto recomendado por Google. Probar antes en un entorno aislado y tener
   lista la reversión a modo reporte si falla una pantalla.
5. Julio autoriza el push/deploy; nadie lo hace automáticamente. Comprobar las
   cabeceras reales y el flujo completo después del despliegue autorizado.

Este documento incorpora la revisión histórica RUT-65 sin integrar su código.
Al combinar ambas ramas, Claude debe resolver el posible conflicto `add/add` de
este archivo y conservar estas notas. Los demás estados de la revisión del día
10 son históricos; la fuente actual del estado de las tarjetas es el kanban.

**Validación local de RUT-87:** el build servido por Django en Chrome cargó login,
Hoy, Pedidos, Planificar y detalle de ruta, con mapa esquemático y sin mensajes
de violación CSP en la consola consultada. El hash de la cabecera coincidió con
el script de tema de la respuesta HTTP real. Se revisó el tema oscuro y su cambio
a claro. No se usó una clave de Google: Maps/Places/Directions en vivo siguen
pendientes de la prueba autorizada previa a enforcement. La sección §15 del PLAN
mencionada por Julio no está en la base `origin/main` 696d02d de esta rama; se
aplicaron las instrucciones de seguridad y entrega de la conversación.
Pruebas: 249 de Django con SQLite (8 nuevas de CSP), 70 de Vitest en 17 archivos,
`npm ci`, TypeScript y build en verde. Las pruebas verifican el hash del HTML
servido, cabeceras también en errores, reporte sin sesión/CSRF, lectura limitada,
límite exacto, JSON inválido y logs sin contenido privado.

## Fuentes

- [Checklist de despliegue de Django](https://docs.djangoproject.com/en/6.0/howto/deployment/checklist/).
- [Validación de contraseñas de Django](https://docs.djangoproject.com/en/6.0/topics/auth/passwords/).
- [Actualización de seguridad Django 6.0.9, 6 de octubre](https://www.djangoproject.com/weblog/2026/oct/06/security-releases/).
- [OSV: consultas de versiones](https://google.github.io/osv.dev/api/).
- [Dominios y HTTPS de Render](https://render.com/docs/custom-domains).
- [CSP: modo reporte y formatos de violación, W3C](https://www.w3.org/TR/CSP/).
- [CSP compatible con Maps JavaScript API, Google](https://developers.google.com/maps/documentation/javascript/content-security-policy).
