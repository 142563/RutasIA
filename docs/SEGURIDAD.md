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
| RUT-85 | Los inicios de sesión por API y `/accounts/login/` no tenían un límite de fallos compartido entre workers. | Guardar contadores en la BD: 5 fallos por cuenta o 20 por IP en una ventana de 15 minutos bloquean 15 minutos. Responder 429 genérico y limpiar únicamente la cuenta tras un éxito. |

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
| Alta | Intentos de inicio de sesión (RUT-85) | Corrección local preparada para API y `/accounts/login/`, pendiente de revisión/integración y verificación de los proxies de Render antes del despliegue. El almacén es la BD; no usa caché por proceso. |
| Alta | Contraseñas de Configuración | `_check_password` solo exige 10 caracteres; `create_user` no ejecuta por sí solo los validadores de Django. Aplicar `validate_password` al crear/cambiar contraseñas y probar contraseñas comunes, numéricas y similares al usuario. |
| Alta | Separar bases (RUT-38) | Entornos distintos en Neon, credenciales distintas y permisos mínimos; impedir que pruebas y datos demo alcancen producción. Verificarlo en los paneles sin publicar la URL privada. |
| Alta | Backups y recuperación | Confirmar retención y respaldo de Neon, probar una restauración en un entorno aislado y documentar cuánto dato/tiempo se puede perder. Un backup sin prueba de restauración no cierra este riesgo. |
| Alta | Cuentas de proveedores | Revisar 2FA, integrantes y permisos en GitHub, Render, Neon, Google, Resend y Spaceship. Rotar claves solo cuando exista evidencia de exposición o corresponda al procedimiento acordado. |
| Media | Política CSP | Diseñar una política compatible con Maps, fuentes locales y el script inicial del tema. Probar primero en modo de reporte; no habilitar una política que rompa el mapa ni dar por protegido el sitio solo por reportar. |
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

### Límite de login preparado en RUT-85

`LoginAttempt` conserva ventanas de marcas de tiempo por cuenta/IP. Sus identificadores usan HMAC con `SECRET_KEY`: no guarda nombres, IP en texto, contraseñas ni un historial ilimitado. La cuenta se normaliza con NFKC, espacios recortados y `casefold` para agrupar variantes conservadoramente; la autenticación sigue las reglas de Django. Rotar `SECRET_KEY` cambia estos identificadores y reinicia los límites asociados.

Los bloqueos de fila de PostgreSQL se adquieren siempre en el mismo orden y se mantienen durante la comprobación de contraseña, con transacción atómica. SQLite inicia la escritura antes de leer los contadores y reintenta brevemente si otra conexión bloquea la BD; al agotar esos reintentos rechaza el intento con 429. No hay llamadas a Google ni Resend. Los rechazos durante un bloqueo no lo prolongan ni ejecutan la comprobación de contraseña. Un éxito elimina los fallos de esa cuenta, conservando los fallos de la IP.

**Confianza de IP:** `LOGIN_TRUSTED_PROXY_CIDRS` es una lista de redes separadas por comas, vacía por defecto. Con ese valor se usa `REMOTE_ADDR` y se ignora `X-Forwarded-For`. Solo si el socket pertenece a una red explícitamente confiable se recorre la cabecera desde la derecha y se toma la primera IP no confiable, descartando prefijos que pueda inventar el cliente. Una cabecera mal formada vuelve a la IP del socket. No se inventaron redes de Render ni se confía automáticamente en direcciones privadas, loopback o una variable de entorno que diga Render.

**Antes de desplegar, Julio debe confirmar los CIDR de los proxies y cómo Render elimina/anexa cabeceras** y configurar la lista. Sin esa configuración, distintos clientes detrás del mismo proxy comparten el límite de 20 fallos por IP; es una limitación operativa que puede bloquearlos juntos. No basta asumir que la primera IP de una cabecera es fiable; no se probó esta configuración en producción.

Limpia los contadores inactivos con `python manage.py clean_login_attempts`: elimina los que no tuvieron actividad en 24 horas y cuyo bloqueo ya venció. Debe programarse en el entorno correspondiente; esta tarjeta no modifica el cron de Render ni se conecta a Neon. El límite reduce los intentos de fuerza bruta; el bloqueo por cuenta también permite negar temporalmente acceso a una cuenta conocida y no sustituye 2FA ni protección de solicitudes en el proxy. El login del administrador `/admin/login/` y el acceso demo no se modifican en esta tarjeta.

**Integración por Claude:** esta rama nace en `696d02d`, crea `0014_login_attempt` y recupera este documento desde RUT-65 (`bc75068`) para actualizar su fila. Hay posibles conflictos add/add de `docs/SEGURIDAD.md`, migraciones `0014_*` paralelas y `app_views.api_login` con RUT-70. Conserva el flujo de contraseña temporal de RUT-70 y coloca su autenticación dentro del límite compartido; no sustituya toda la función. No se integró RUT-65 ni se cambiaron sus ajustes HTTPS/SECRET_KEY. Los commits son locales, sin push ni merge; Claude integra y Julio autoriza el despliegue.

Se leyeron `CLAUDE.md`, `PLAN.md` §14 y el documento de seguridad anterior. La sección 15 mencionada en las instrucciones recientes no existe en la base `696d02d` de esta rama; se aplicaron las reglas de seguridad comunicadas en el prompt y el alcance de RUT-85, sin inventar contenido de esa sección.

**Verificación local de RUT-85:** 256 pruebas Django en verde (184.058 s), incluidas 15 nuevas para umbrales, IP, mensaje genérico, vencimiento, ventana móvil, limpieza por éxito, CSRF, login HTML y dos conexiones concurrentes de SQLite. Una IP bloqueada tampoco puede crear contadores de cuentas nuevas cambiando el usuario. `makemigrations --check --dry-run` no detecta cambios. Frontend: `npm ci`, TypeScript, 70 pruebas Vitest en 17 archivos y build correctos. No se ejecutaron pruebas contra PostgreSQL/Neon ni se probó el proxy real; esas comprobaciones siguen pendientes de integración y despliegue autorizado. Los avisos existentes son `staticfiles` local inexistente y chunk inicial de 508.23 kB. `npm ci` reporta el aviso alto de `source-map-js` 1.2.1 de la base; RUT-83 prepara el parche 1.2.2 en su propia rama, sin mezclarse con esta tarjeta.

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

## Fuentes

- [Checklist de despliegue de Django](https://docs.djangoproject.com/en/6.0/howto/deployment/checklist/).
- [Validación de contraseñas de Django](https://docs.djangoproject.com/en/6.0/topics/auth/passwords/).
- [Actualización de seguridad Django 6.0.9, 6 de octubre](https://www.djangoproject.com/weblog/2026/oct/06/security-releases/).
- [OSV: consultas de versiones](https://google.github.io/osv.dev/api/).
- [Dominios y HTTPS de Render](https://render.com/docs/custom-domains).
