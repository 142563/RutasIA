# LogistiRoute (Python + Django)

Sistema web para monitoreo y optimización de rutas de distribución en Guatemala.

## Funcionalidades implementadas
- Registro y consulta de departamentos, rutas de conexión, vehículos y pedidos.
- Planificación de viajes con cálculo de ruta óptima usando algoritmo de Dijkstra.
- Estimación automática de distancia total, combustible y costo del viaje.
- Monitoreo de viajes por estados: `planned`, `in_progress`, `completed`, `canceled`.
- Registro de eventos de seguimiento por viaje.
- Dashboard con métricas operativas y gráficas.
- Interfaz web integrada (frontend) dentro de Django.

## Requisitos
- Python 3.12+
- Django 6.0.4+

## Instalación y ejecución
1. Instalar dependencias:
   ```bash
   python -m pip install -r requirements.txt
   ```
2. Configurar base de datos (opcional pero recomendado para Neon):
   Crea un archivo `.env` en la raíz del proyecto:
   ```env
   DATABASE_URL=postgresql://USER:PASSWORD@HOST/DBNAME?sslmode=require&channel_binding=require
   ```
   Si no se define `DATABASE_URL`, Django usa SQLite local (`db.sqlite3`).
3. Aplicar migraciones:
   ```bash
   python manage.py migrate
   ```
4. Cargar datos demo:
   ```bash
   python manage.py seed_demo_data
   ```
5. Ejecutar servidor:
   ```bash
   python manage.py runserver
   ```
6. Abrir en navegador:
   ```text
   http://127.0.0.1:8000/
   ```

## Estructura principal
- `rutasia/`: configuración del proyecto Django.
- `logistics/`: modelos, servicios de negocio (Dijkstra), vistas y API.
- `templates/logistics/`: vista principal del frontend.
- `static/logistics/`: estilos y JavaScript de la interfaz.

## Deploy en Render
1. Sube este repo a GitHub.
2. Crea un Web Service en Render conectado al repo.
3. Usa estos comandos:
   - Build Command:
     ```bash
     pip install -r requirements.txt && python manage.py collectstatic --noinput
     ```
   - Start Command:
     ```bash
     python manage.py migrate && gunicorn rutasia.wsgi:application --bind 0.0.0.0:$PORT --workers 3 --timeout 120
     ```
4. Configura variables de entorno en Render:
   - `DATABASE_URL` = tu cadena de Neon
   - `SECRET_KEY` = una clave nueva
   - `DEBUG` = `False`
   - `ALLOWED_HOSTS` = `tu-app.onrender.com`
   - `CSRF_TRUSTED_ORIGINS` = `https://tu-app.onrender.com`

