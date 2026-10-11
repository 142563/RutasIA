# Seguridad de enruta

> Resumen para la defensa (actualizado 2026-10-11, épica RUT-84). Estado: ✓ hecho · ◐ en revisión o en curso · ☐ pendiente.
> El detalle técnico y la auditoría de Codex (10 de octubre) siguen más abajo.

## Qué protege hoy a enruta (por capas)

| Capa | Medida | Estado |
|---|---|---|
| Acceso | Sesión de Django (cookie HttpOnly, 8 h, expira al cerrar el navegador); cookies `Secure` en producción. | ✓ |
| Acceso | Roles verificados en el **backend** en cada API (admin, despachador, conductor); el conductor solo ve y modifica su ruta. | ✓ |
| Acceso | Login de demostración apagado en producción; no concede privilegios aunque la cuenta se promueva (RUT-64). | ✓ |
| Acceso | Contraseña temporal por correo que vence en 72 h y cambio obligatorio al primer ingreso; validadores de contraseña de Django (RUT-70). | ◐ |
| Acceso | Límite de intentos de inicio de sesión con almacén compartido (RUT-85). | ☐ |
| Acceso | Permisos por rol también en las APIs del motor de rutas (RUT-86). | ☐ |
| Acceso | Bitácora de auditoría: quién inició sesión, creó usuarios, asignó o canceló rutas (RUT-88). | ☐ |
| Peticiones | Protección CSRF en todo POST/PATCH/DELETE; cuerpos JSON validados (objeto o 400) (RUT-64). | ✓ |
| Peticiones | SQL solo por el ORM de Django (consultas parametrizadas): sin SQL armado a mano. | ✓ |
| Peticiones | Salida escapada: React escapa por defecto y las plantillas de correo usan el autoescape de Django. | ✓ |
| Transporte | HTTPS con certificado de Render en enruta.world; redirección a HTTPS y HSTS de 1 h en Django (RUT-65). | ◐ |
| Transporte | Cabeceras `X-Frame-Options: DENY`, `nosniff`, `Referrer-Policy`. Política CSP en modo reporte (RUT-87). | ✓ / ☐ |
| Secretos | Llaves solo en variables de entorno de Render (`SECRET_KEY`, `DATABASE_URL`, Google, Resend); nunca en Git (`.env` ignorado). | ✓ |
| Secretos | Key de Google del navegador restringida por dominio (enruta.world, onrender.com, localhost) y por APIs; key del servidor separada, solo Routes API, nunca llega al navegador. | ✓ |
| Secretos | `SECRET_KEY` privada obligatoria en producción (la app no arranca con la de desarrollo) (RUT-65). | ◐ |
| Datos | Seguimiento público del cliente con token de 128 bits; muestra datos mínimos (sin teléfonos, dirección completa ni coordenadas) (RUT-71). | ◐ |
| Datos | Bitácora de correos sin cuerpos; la contraseña temporal nunca se guarda ni se registra (RUT-69/70). | ✓ / ◐ |
| Datos | Retención y minimización de datos personales y logs (RUT-89). | ☐ |
| Dependencias | Django actualizado a la última versión de seguridad de la serie 6.0 (RUT-66); `npm audit` del frontend sin avisos conocidos. | ◐ |
| Infraestructura | Base de producción separada de la de desarrollo (RUT-38); respaldos con prueba de restauración (RUT-90). | ☐ |
| Infraestructura | 2FA y permisos mínimos en GitHub, Render, Neon, Google, Resend y Spaceship; cuotas y alertas de gasto en Google (RUT-91). | ☐ |
| Operación | Monitoreo y alertas de errores 500, correos fallidos, cron de tráfico y certificados (RUT-92). | ☐ |

**Para defender ante el jurado:** la seguridad está en capas (si una falla, la siguiente contiene el daño): quién entra (sesión + rol en el backend), qué puede pedir (CSRF, validación, ORM), por dónde viaja (HTTPS/HSTS), dónde viven los secretos (variables de entorno, llaves restringidas) y qué datos se exponen (mínimos, con token no adivinable). Lo pendiente está priorizado en el kanban (épica RUT-84).

---

## Auditoría de Codex (10 de octubre de 2026)

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
| Media | Permisos de APIs del motor | Los endpoints de ruteo requieren sesión, pero no todos restringen el rol. Decidir cuáles necesita el conductor y probar que los restantes queden limitados a despacho/administración. `optimize` ya limita a 50 paradas. |
| Media | Costos y abuso de Google/Resend | Restringir la key del navegador por dominio y APIs; la key del servidor no debe llegar al frontend. Configurar cuotas, presupuestos y alertas. La caché de comprobación de tráfico es local por proceso: revisar concurrencia y almacén compartido. |
| Media | Datos personales y logs | Definir retención de nombres, teléfonos, direcciones, correos y firmas impresas. Los logs de notificaciones pueden incluir destinatarios y asuntos: reducirlos o limitar su acceso/retención. |
| Media | Monitoreo operativo | Alertas ante errores 500, fallos de correo, cron de tráfico y expiración de certificados. Verificar copias de seguridad y cron con evidencia periódica. |

Actualización 2026-10-11: el dominio enruta.world está verificado en Resend y
`RESEND_API_KEY` ya está en Render (la pegó Julio directamente en el panel, nunca en
el chat ni en Git). RUT-63 se cerró: la absorbió la épica de correos por rol (RUT-68).
Falta la prueba de punta a punta de los correos (RUT-73).

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

## Fuentes

- [Checklist de despliegue de Django](https://docs.djangoproject.com/en/6.0/howto/deployment/checklist/).
- [Validación de contraseñas de Django](https://docs.djangoproject.com/en/6.0/topics/auth/passwords/).
- [Actualización de seguridad Django 6.0.9, 6 de octubre](https://www.djangoproject.com/weblog/2026/oct/06/security-releases/).
- [OSV: consultas de versiones](https://google.github.io/osv.dev/api/).
- [Dominios y HTTPS de Render](https://render.com/docs/custom-domains).
