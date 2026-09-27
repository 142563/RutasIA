# Empezar a programar en tu compu (Windows)

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
 └── dev  ← integración
      ├── feature/motor-grafo
      ├── feature/dijkstra-astar
      └── feature/frontend-react …
```

Cada funcionalidad va en su rama desde `dev`, con un PR hacia `dev`. Cuando `dev` esté estable, se hace el PR de `dev` a `main`.

## Enlaces útiles

- Plan: `docs/PLAN.md`
- Prototipo navegable (lienzo): https://claude.ai/artifact/EsmmFBakudic3pUQBT5GrK
- Pantallas del prototipo como archivos: `docs/prototipo/`
