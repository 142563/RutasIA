# Empezar a programar en tu compu (Windows)

La app en producción está en **[https://enruta.world](https://enruta.world)**, alojada en Render. Los DNS se administran en Spaceship; los correos de entrega usan Resend.

## Versión corta (lo único que necesitas para usar la app)

Necesitas **Python 3.12+** y **Node.js 20+**. En la carpeta del proyecto:

```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env          # pon tu GOOGLE_MAPS_API_KEY para ver Google Maps
python manage.py preparar       # base de datos, grafo, tráfico, usuarios y app React: todo en uno
python manage.py runserver
```

Abre http://127.0.0.1:8000 y toca **Despachador** o **Conductor**: entras sin contraseña, porque en tu compu está el modo demo. Ya hay una ruta de ejemplo en curso. Si quieres entrar escribiendo el usuario, la contraseña te la muestra `preparar` y queda en `.env` como `DEMO_PASSWORD`.

Para la defensa en Render, los botones de demo se activan con la variable `DEMO_LOGIN=True`. Solo existen para el despachador y el conductor, nunca para el administrador.

**Las siguientes veces solo necesitas:** `.venv\Scripts\activate` y `python manage.py runserver`. Si bajas cambios de GitHub (`git pull`), vuelve a correr `python manage.py preparar`: no borra nada.

Cómo funciona todo, explicado simple: [`COMO_FUNCIONA.md`](COMO_FUNCIONA.md).

---

## 1. Crear tu propia copia y rama

Codex trabaja en una copia aparte. Nunca uses `C:\Users\Julio Ticas\Documents\Repositorios\RutasIA`: esa carpeta la usa Claude. En tu propia copia, reemplaza `<n>` por el número de la tarjeta:

```powershell
git fetch origin
git checkout -b codex/rut-<n> origin/main
```

Si no lo tienes:

```powershell
git clone https://github.com/142563/RutasIA.git RutasIA-Codex
cd RutasIA-Codex
git fetch origin
git checkout -b codex/rut-<n> origin/main
```

## 2. Entorno de Python (3.12 o superior)

Django 6 **no funciona con Python 3.11 o anterior**. Verifica con `python --version`.

```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

## 3. Variables de entorno

```powershell
copy .env.example .env
```

Abre `.env`. Sin las keys de Google puedes desarrollar con el mapa esquemático y datos estimados. Deja `DATABASE_URL=` vacía para usar SQLite local. Nunca copies la conexión de producción para correr pruebas.

| Variable | Para qué sirve | ¿Obligatoria? | Ejemplo sin secretos |
|---|---|---|---|
| `SECRET_KEY` | Protege las sesiones de Django | Sí en producción; genera una propia | `<clave aleatoria privada de al menos 50 caracteres>` |
| `DEBUG` | Muestra detalles de errores en desarrollo | `False` en producción | `True` local / `False` Render |
| `ALLOWED_HOSTS` | Dominios que acepta Django, separados por coma | Sí para el dominio propio | `enruta.world,www.enruta.world,rutasia.onrender.com` (local: `127.0.0.1,localhost`) |
| `CSRF_TRUSTED_ORIGINS` | Orígenes HTTPS confiables para formularios | Configura los dominios de producción | `https://enruta.world,https://www.enruta.world` (local: vacío) |
| `DATABASE_URL` | Conexión privada a PostgreSQL/Neon | Sí en Render; vacía usa SQLite | Vacío local; `<conexión privada de Neon>` en Render |
| `GOOGLE_MAPS_API_KEY` | Mapa de fondo, Places y Directions en el navegador | Solo para Google Maps visual | Vacío / `<key del navegador restringida por dominio>` |
| `GOOGLE_MAPS_MAP_ID` | Identificador del mapa para marcadores | Opcional; tiene valor por defecto | `DEMO_MAP_ID` local; ID propio en producción |
| `GOOGLE_ROUTES_API_KEY` | Construye el grafo y calibra tráfico con Routes API | Solo para datos reales de Google | Vacío / `<key privada del servidor>` |
| `DEMO_PASSWORD` | Crea usuarios de demostración | Solo al preparar esos usuarios | `<contraseña propia de demo>` |
| `DEMO_LOGIN` | Habilita entrar sin contraseña como despachador/conductor | Opcional; por defecto sigue `DEBUG` | `False` en producción; `True` solo para la defensa autorizada |
| `RESEND_API_KEY` | Autoriza el envío de correos | Solo para enviar de verdad | Vacío local / `<key privada de Resend>` |
| `NOTIFY_FROM` | Remitente del correo; exige dominio verificado | Opcional; tiene valor por defecto | `enruta <entregas@enruta.world>` |
| `SITE_URL` | Base del enlace a la ruta en el correo | Ajusta al entorno | `http://127.0.0.1:8000` local / `https://enruta.world` Render |

En Render, configura los secretos en **Environment**, nunca en Git. `render.yaml` declara las keys como `sync: false` (se ingresan aparte), `DEBUG=False`, `NOTIFY_FROM` y `SITE_URL`. **No declara `ALLOWED_HOSTS` ni `CSRF_TRUSTED_ORIGINS`: agrégalas en el panel del servicio web** con los dominios de la tabla. Esta guía no cambia la configuración del servidor.

### Probar correos en local sin enviarlos

1. Usa tu base SQLite y deja `RESEND_API_KEY=` vacía; pon `SITE_URL=http://127.0.0.1:8000`.
2. Crea un pedido de prueba con un correo ficticio, por ejemplo `cliente@example.invalid`, y asígnalo a una ruta. También puede tener correo el usuario despachador que creó la ruta; los usuarios de demo vienen sin correo.
3. Inicia la ruta como conductor y marca una parada como **Entregada**. La entrega queda guardada; sin la key no se llama a Resend. Una parada fallida no dispara estos correos.
4. Revisa el registro de `logistics.application.notifications` a nivel `INFO`: indica cuántos correos no se enviaron. No muestra una vista previa del mensaje. Si tu consola no muestra `INFO`, inicia el servidor local así (también fuerza SQLite y desactiva Resend aunque `.env` tenga otros valores):

```powershell
python -c 'import logging,os,runpy,sys; logging.basicConfig(level=logging.INFO); os.environ["DATABASE_URL"]=""; os.environ["RESEND_API_KEY"]=""; sys.argv=["manage.py","runserver","--noreload"]; runpy.run_path("manage.py",run_name="__main__")'
```

Las pruebas automatizadas de notificaciones simulan Resend; no necesitan una key ni envían correos. El comportamiento actual (RUT-55) avisa de la entrega al cliente y al despachador creador, si tienen correo. Los demás avisos por rol de `PLAN.md` §14 son trabajo pendiente, no funcionalidad disponible.

### Dominio y DNS

DNS es la agenda que conecta un nombre como `enruta.world` con su servidor. En **Spaceship**, los registros web apuntan a Render; los de correo permiten que Resend firme y autentique el remitente:

| Registro | Nombre | Destino o función |
|---|---|---|
| A | `@` (enruta.world) | `216.24.57.1`, dirección de Render; confirma el valor en Custom Domains si se reconfigura |
| CNAME | `www` | `rutasia.onrender.com`, servicio web de Render |
| TXT (DKIM) | `resend._domainkey` | Firma del correo: copia el valor que muestra Resend en Spaceship; no se reproduce aquí |
| CNAME (SPF/Return-Path) | `send` y `rsend` | En esta configuración apuntan a `send.forge.rmta.net` y `rsend.forge.rmta.net`; usa siempre el tipo y valor indicados por Resend |
| TXT (DMARC) | `_dmarc` | `v=DMARC1; p=none` para monitoreo inicial; no bloquea mensajes falsificados |

Los CNAME de Resend delegan su autenticación; no agregues un TXT SPF en el mismo nombre que un CNAME. Comprueba los estados de verificación en los paneles de Render y Resend; que la web abra no garantiza que el correo esté habilitado. Render gestiona el certificado HTTPS. Una política DMARC más estricta requiere verificar primero los envíos legítimos.

Referencias: [dominios en Render](https://render.com/docs/custom-domains), [verificación en Resend](https://resend.com/docs/dashboard/domains/introduction), [Return-Path](https://resend.com/docs/dashboard/domains/custom-return-path) y [DMARC](https://resend.com/docs/dashboard/domains/dmarc).

## 4. Levantar y probar

```powershell
python manage.py migrate
python manage.py seed_demo_data
python manage.py createsuperuser
python -c 'import os,runpy,sys; os.environ["DATABASE_URL"]=""; sys.argv=["manage.py","test","--noinput"]; runpy.run_path("manage.py",run_name="__main__")'
python manage.py runserver
```

Abre http://127.0.0.1:8000

## 4a. Aplicación React (frontend/)

Necesitas Node.js 20 o superior.

```powershell
cd frontend
npm ci
npm run dev
```

Abre http://localhost:5173 (Vite reenvía `/api` a Django en el puerto 8000, así que `runserver` debe estar corriendo).

Usuarios de demo: pon una contraseña en `DEMO_PASSWORD` dentro de `.env` y corre `python manage.py seed_demo_users`. Se crean `admin`, `despachador` y `conductor`.

Para que Django sirva la app como en producción: `npm run build` (queda en `frontend/dist/app/`) y abre http://127.0.0.1:8000.

Verificación del frontend antes de cada commit: `npm ci`, `npx tsc -b`, `npx vitest run` y `npm run build`. Para las pruebas de gráficas del backend instala también `pip install -r requirements-dev.txt`.

## 4b. Grafo nacional y experimentos

Sin key de Google (datos **estimados y sintéticos**, solo para desarrollar):

```powershell
python manage.py seed_graph_nodes
python manage.py build_graph --estimate
python manage.py calibrate_traffic --synthetic
pip install -r requirements-dev.txt
python manage.py run_experiments --max-nodes 10000
```

Con `GOOGLE_ROUTES_API_KEY` en `.env` (datos reales, para la tesis). Cómo conseguir las keys, paso a paso: [`docs/GOOGLE_KEYS.md`](GOOGLE_KEYS.md). Primero verifícala con `python manage.py check_google`:

```powershell
python manage.py build_graph
python manage.py calibrate_traffic
python manage.py run_experiments
```

Los resultados quedan en `experiments/output/` (CSV + PNG). Cada CSV trae la columna `data_source`.

## 5. Programar con Claude Code

```powershell
claude
```

Claude Code lee `CLAUDE.md` automáticamente, así que ya conoce el plan, las reglas del motor y el estilo de diseño.

**Primer mensaje sugerido** (día 1 del cronograma, en `docs/PLAN.md` §10):

> Lee CLAUDE.md completo, docs/PLAN.md §14 y la tarjeta del kanban. Trabaja en tu propia copia, en codex/rut-<n> desde origin/main. Respeta su alcance y NO TOCAR. Verifica backend con SQLite y frontend; deja un commit local para revisión, sin push ni merge.

**Mensajes siguientes**, uno por día del cronograma:

- *Día 2:* "Implementa `build_graph` con Google Routes API según §2.3.1, con caché y sin llamar a Google dentro del algoritmo."
- *Día 3:* "Implementa Dijkstra y A\* en `logistics/routing/` según §2.4, §2.5 y el checklist §2.9, con la prueba E1."
- …y así con cada día.

## Flujo de ramas

```
main  ← Claude integra localmente después de revisar
 └── codex/rut-<n>  ← trabajo y commits locales de Codex
```

**Regla de Julio desde el 2026-10-11:** trabaja en tu propia copia, desde `origin/main`. Con todas las verificaciones en verde, haz el commit en español, en imperativo y terminado en `(RUT-<n>)`. Actualiza la documentación y el kanban con la evidencia, deja la tarjeta en **En revision** y comunica a Julio la rama y el hash. Claude revisa e integra a `main` localmente. **Codex no hace push, merge a main ni abre PR. Nadie hace push sin autorización de Julio**: Render despliega automáticamente cada push a `main`.

La rama `archivo/Dev-2026-07` guarda el prototipo de julio; no se borra.

## Enlaces útiles

- Plan: `docs/PLAN.md`
- Prototipo navegable (lienzo): https://claude.ai/artifact/EsmmFBakudic3pUQBT5GrK
- Pantallas del prototipo como archivos: `docs/prototipo/`
