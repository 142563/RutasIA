# Empezar a programar en tu compu (Windows)

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

## 1. Traer la rama `dev`

Si ya tienes el repo clonado:

```powershell
cd "C:\Users\julio\OneDrive\Desktop\Proyecto Rutas\RutasIA"
git fetch origin
git checkout dev
git pull origin dev
```

Si no lo tienes:

```powershell
git clone https://github.com/142563/RutasIA.git
cd RutasIA
git checkout dev
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

Abre `.env` y llena como mínimo `GOOGLE_MAPS_API_KEY`. Si dejas `DATABASE_URL` vacía, se usa SQLite local, que es ideal para desarrollar.

## 4. Levantar y probar

```powershell
python manage.py migrate
python manage.py seed_demo_data
python manage.py createsuperuser
python manage.py test
python manage.py runserver
```

Abre http://127.0.0.1:8000

## 4a. Aplicación React (frontend/)

Necesitas Node.js 20 o superior.

```powershell
cd frontend
npm install
npm run dev
```

Abre http://localhost:5173 (Vite reenvía `/api` a Django en el puerto 8000, así que `runserver` debe estar corriendo).

Usuarios de demo: pon una contraseña en `DEMO_PASSWORD` dentro de `.env` y corre `python manage.py seed_demo_users`. Se crean `admin`, `despachador` y `conductor`.

Para que Django sirva la app como en producción: `npm run build` (queda en `frontend/dist/app/`) y abre http://127.0.0.1:8000.

Pruebas del frontend: `npm test` (Vitest) y `npm run build` (revisa tipos).

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

> Lee docs/PLAN.md completo. Vamos con la Semana 1, Día 1: crea una rama `feature/motor-grafo` desde `dev`. Crea los modelos `Node`, `Edge` y `TrafficProfile` según §6 y propón la lista inicial de nodos (22 cabeceras + municipios clave + cruces de carreteras) con coordenadas, como datos semilla. No toques todavía el frontend. Usa modo plan primero.

**Mensajes siguientes**, uno por día del cronograma:

- *Día 2:* "Implementa `build_graph` con Google Routes API según §2.3.1, con caché y sin llamar a Google dentro del algoritmo."
- *Día 3:* "Implementa Dijkstra y A\* en `logistics/routing/` según §2.4, §2.5 y el checklist §2.9, con la prueba E1."
- …y así con cada día.

## Flujo de ramas

```
main  ← producción (Render)
 └── dev  ← aquí se trabaja
```

**Mientras el proyecto no esté en producción, se trabaja directo en `dev`, sin pull requests:** pruebas en verde (`python manage.py test`) → commit → `git push origin dev`. Cuando `dev` esté estable, se lleva a `main` para el deploy. A partir de ahí, cada funcionalidad nueva irá en su propia rama con PR hacia `dev`.

La rama `archivo/Dev-2026-07` guarda el prototipo de julio (no está en `dev`); no se borra.

## Enlaces útiles

- Plan: `docs/PLAN.md`
- Prototipo navegable (lienzo): https://claude.ai/artifact/EsmmFBakudic3pUQBT5GrK
- Pantallas del prototipo como archivos: `docs/prototipo/`
