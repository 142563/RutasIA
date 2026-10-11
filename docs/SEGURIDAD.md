# Seguridad de enruta: revisión del 10 de octubre de 2026

Actualización C2 (RUT-86), 11 de octubre: commit local en `codex/rut-86`,
sin push ni merge. Claude revisa e integra; solo Julio autoriza desplegar.

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
| Media | Política CSP | Diseñar una política compatible con Maps, fuentes locales y el script inicial del tema. Probar primero en modo de reporte; no habilitar una política que rompa el mapa ni dar por protegido el sitio solo por reportar. |
| Media | Permisos de APIs del motor (RUT-86, preparado) | Los siete endpoints de esta base quedan restringidos a admin/despachador, con 403 en español antes de parsear o ejecutar búsquedas. La tabla de pruebas cubre cada endpoint, los tres roles, ausencia de perfil, superusuario y sesión anónima. `optimize` conserva su límite de 50 paradas. |
| Media | Costos y abuso de Google/Resend | Restringir la key del navegador por dominio y APIs; la key del servidor no debe llegar al frontend. Configurar cuotas, presupuestos y alertas. La caché de comprobación de tráfico es local por proceso: revisar concurrencia y almacén compartido. |
| Media | Datos personales y logs | Definir retención de nombres, teléfonos, direcciones, correos y firmas impresas. Los logs de notificaciones pueden incluir destinatarios y asuntos: reducirlos o limitar su acceso/retención. |
| Media | Monitoreo operativo | Alertas ante errores 500, fallos de correo, cron de tráfico y expiración de certificados. Verificar copias de seguridad y cron con evidencia periódica. |

La revisión original dejó pendiente verificar Resend, configurar su API key
en Render y probar el correo de punta a punta. RUT-63 se cerró sin implementar,
absorbida por la épica de avisos. La key debe introducirla Julio directamente en el panel;
no debe pegarse en el chat ni en Git.

Para la tesis, también siguen pendientes la precisión E4 (RUT-43), validación de
coordenadas/tramos (RUT-20) y cierre de experimentos (RUT-17). Una interfaz pulida
no demuestra precisión del modelo; los datos sintéticos deben seguir señalados.

## Comprobaciones antes de integrar y desplegar

### Matriz de acceso del motor en RUT-86

| Endpoint | Admin/despachador | Conductor |
| --- | --- | --- |
| GET `/api/routing/nodes/` | Sí | 403 |
| POST `/api/routing/route/` | Sí | 403 |
| POST `/api/routing/compare/` | Sí | 403 |
| POST `/api/routing/explore/` | Sí | 403 |
| POST `/api/routes/optimize/` | Sí | 403 |
| GET `/api/routing/best-departure/` | Sí | 403 |
| GET `/api/traffic/profile/` | Sí | 403 |

Las vistas actuales del conductor (`DriverTodayPage`, `DriverStopPage`,
`ReportIncident`, `AlternativeRouteNotice`) consumen `/api/driver/*`, incidentes
y decisiones de recálculo; ninguna llama a estos siete endpoints. Su ruta ya
incluye los datos que necesitan. Una cuenta sin perfil conserva el rol con
menos permisos; un superusuario sin perfil conserva acceso administrativo.

RUT-78 incorporará un mapa propio: al integrar esa tarjeta se debe justificar
y probar cualquier permiso adicional de lectura para conductor, sin darle
acceso a las herramientas genéricas de búsqueda/optimización. Geometría
(RUT-75) se prepara en otra rama y no existe en esta base; revisar su endpoint
en esa integración. `routing_views.py` y este documento requieren combinación
con las otras ramas. El documento parte de RUT-65, aún pendiente de integrar;
no se copiaron sus cambios de configuración a esta rama.

Verificación C2: 244 pruebas Django con SQLite y 70 Vitest en 17 archivos;
`npm ci`, TypeScript y build correctos. Permanece el aviso de bundle y el aviso
de source-map-js de la base, cuyo parche está separado en RUT-83. §15 de
`PLAN.md` todavía no existe en `origin/main` 696d02d; se aplicaron las reglas
de seguridad de Julio y la tarjeta, sin inventar esa sección.

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
