# Plan de rediseño — Sistema de optimización de rutas para paquetería

> Proyecto de graduación · Plan de trabajo a 3 semanas
> Estado: **planificación** (aún no se modifica código)

---

## 1. Visión

Pasar de un sistema que calcula **el camino más corto entre dos departamentos** a una plataforma que resuelve el problema real de una empresa de paquetería:

> *"Tengo una bodega, N paquetes con direcciones reales y K vehículos. ¿Qué paquetes lleva cada vehículo y en qué orden los entrega para recorrer la menor distancia posible?"*

Esto es un **Problema de Ruteo de Vehículos con Capacidad (CVRP)**, con una experiencia de usuario moderna y separada por roles: quien planifica (despachador) y quien entrega (conductor).

### Decisiones tomadas

| # | Decisión | Resultado |
|---|----------|-----------|
| 1 | Nombre / marca | Crear uno **nuevo desde cero** (ver §2) |
| 2 | Alcance del algoritmo | **Multi-parada** (VRP) con direcciones reales |
| 3 | Frontend | **React** (SPA) consumiendo la API de Django |
| 4 | Plazo | ~3 semanas |
| 5 | Conductor | Rol propio con su usuario y **vista propia** (móvil) |

---

## 2. Nombre y marca (pendiente de elegir)

Propuestas creadas desde cero:

| Nombre | Idea detrás | Comentario |
|--------|-------------|------------|
| **Enruta** | Del verbo *enrutar*: "poner en ruta" | Corto, en español, dice exactamente qué hace |
| **Trayecta** | De *trayecto* | Suena a producto, fácil de recordar |
| **Vértice** | Término de teoría de grafos (nodos) | Conecta con la parte académica del algoritmo |
| **Rumbo** | "Llevar rumbo", dirección | Muy simple, cálido |
| **Ruvia** | Ruta + vía | Inventado, único, fácil de registrar |

Una vez elegido: logo (isotipo + wordmark), paleta, tipografía y favicon. Se eliminan los 3 logos actuales y todas las menciones a *Rutas A\**, *JaironRoute* y *LogistiRoute*.

---

## 3. Roles y permisos

Los roles actuales (admin, supervisor, operador) se reorganizan y se agrega **conductor**. Un conductor es un `User` enlazado a un `Driver`.

| Módulo | Administrador | Despachador | Conductor |
|--------|:---:|:---:|:---:|
| Inicio / KPIs | ✅ | ✅ | — |
| Pedidos (crear, editar, cancelar) | ✅ | ✅ | — |
| Planificador de rutas | ✅ | ✅ | — |
| Rutas / viajes (todas) | ✅ | ✅ | — |
| Monitoreo en vivo | ✅ | ✅ | — |
| Flota (vehículos, conductores) | ✅ | ✅ (ver) | — |
| Reportes | ✅ | ✅ | — |
| Configuración (usuarios, bodegas, combustible) | ✅ | — | — |
| **Mi ruta de hoy** | — | — | ✅ |
| **Marcar entregas** | — | — | ✅ |
| Mi historial | — | — | ✅ |

> El rol *supervisor* actual pasa a ser *despachador*. Si luego hace falta un rol de solo lectura, se agrega sin cambiar el diseño.

Al iniciar sesión, cada rol llega directo a su pantalla: despachador y administrador a **Inicio**, conductor a **Mi ruta de hoy**.

---

## 4. Alcance funcional (MoSCoW)

### Must — sin esto no hay proyecto
- Pedidos con **dirección real** (autocompletado de Google Places y coordenadas).
- **Bodegas** (punto de salida) configurables.
- **Optimizador multi-parada**: asignar pedidos a vehículos respetando la capacidad y ordenar paradas.
- **Comparación**: ruta sin optimizar vs. optimizada (km, tiempo, costo de combustible, % de ahorro).
- Planificador visual centrado en el mapa, con rutas por vehículo en colores.
- Vista del conductor: ruta del día, paradas en orden, "Navegar" (abre Google Maps) y marcar **entregado / no entregado (motivo)**.
- Ciclo de vida de la ruta: planificada → en curso → completada / cancelada; estado por parada.
- Login y navegación por rol.

### Should — lo que hace brillar la defensa
- Monitoreo en vivo: progreso de cada ruta (paradas completadas) en el mapa.
- **GPS real del conductor** (geolocalización del navegador) en lugar de solo simulación.
- Dashboard con KPIs y gráficas: km ahorrados, entregas del día, % de éxito, costo.
- Comparar algoritmos del proyecto contra `optimizeWaypoints` de Google como *benchmark*.
- Modo oscuro.

### Could — si sobra tiempo
- Reordenar paradas o moverlas entre vehículos arrastrando (*drag & drop*) antes de confirmar.
- Ventanas horarias de entrega (VRPTW).
- Evidencia de entrega (foto o nombre de quien recibe).
- Importar pedidos desde CSV/Excel.
- Exportar la hoja de ruta en PDF.

### Won't (por ahora)
- App nativa (la vista del conductor será web responsive / PWA).
- Seguimiento público para el cliente final.
- Multi-empresa.

---

## 5. El algoritmo (núcleo académico)

### Entrada
- 1 bodega, N pedidos (lat/lng, peso), K vehículos (capacidad, rendimiento, costo/km).
- **Matriz de distancias/tiempos** entre todos los puntos, desde Google (Routes API `computeRouteMatrix` o Distance Matrix) y guardada en caché. Si falla, se usa Haversine como respaldo.

### Propuesta en dos etapas
1. **Asignación / agrupamiento: algoritmo de ahorros de Clarke-Wright.** Construye rutas por vehículo respetando la capacidad. Es clásico, fácil de explicar y da buenos resultados.
2. **Mejora de cada ruta: vecino más cercano + 2-opt.** Ordena las paradas y luego elimina cruces.
   - *Opcional:* Or-opt o Recocido Simulado (*Simulated Annealing*) como metaheurística para ir un paso más allá.

### Qué se mide y se muestra (para el documento de tesis)
| Métrica | Contra qué se compara |
|---------|-----------------------|
| Distancia total (km) | Orden de captura (sin optimizar) |
| Tiempo estimado | Google `optimizeWaypoints` (límite de ~25 paradas) |
| Costo de combustible (Q) | Vecino más cercano solo vs. + 2-opt |
| Tiempo de cómputo (ms) | Crecimiento con N = 10, 25, 50, 100 |

### ¿Qué pasa con Dijkstra y A\*?
Se conservan en el documento como la **fase 1** del proyecto (camino más corto en grafo). En la nueva versión, la distancia entre dos direcciones la resuelve el motor de rutas de Google (que internamente usa algoritmos de esa familia). El aporte propio pasa a ser **la asignación y el orden de las paradas**, que es el problema difícil (NP-hard).

---

## 6. Arquitectura técnica

### Stack propuesto

| Capa | Tecnología | Por qué |
|------|-----------|---------|
| Frontend | **React + Vite + TypeScript** | Moderno, rápido, tipado |
| Estilos | **Tailwind CSS + shadcn/ui** | Componentes accesibles y bonitos sin diseñarlos desde cero |
| Ruteo | React Router | URLs por pantalla |
| Datos del servidor | TanStack Query | Caché, *loading* y reintentos automáticos |
| Formularios | react-hook-form + zod | Validación clara |
| Mapa | `@vis.gl/react-google-maps` | Integración de Google Maps pensada para React |
| Gráficas | Recharts | Sencillo y suficiente |
| Íconos | lucide-react | Consistentes con shadcn |
| Backend | **Django (se mantiene)** como API JSON | Reutiliza modelos, auth y lógica |
| Base de datos | PostgreSQL (Neon), se mantiene | — |
| Deploy | Render, **un solo servicio** | Django sirve la API y el build de React (sin CORS) |

### Estructura de carpetas
```
RutasIA/
├── rutasia/            # settings Django (se mantiene)
├── logistics/          # app Django: modelos, API, algoritmos
│   └── domain/vrp/     # NUEVO: Clarke-Wright, 2-opt, matriz de distancias
├── frontend/           # NUEVO: app React (Vite)
│   ├── src/
│   │   ├── app/        # router, layout, providers
│   │   ├── features/   # pedidos, planificador, rutas, conductor, ...
│   │   ├── components/ # UI compartida (design system)
│   │   └── lib/        # cliente API, utilidades
│   └── ...
└── docs/PLAN.md
```

### Autenticación
Sesión de Django + CSRF (mismo dominio, sin tokens JWT). Endpoints `api/auth/login`, `api/auth/logout` y `api/me` (devuelve rol y conductor enlazado).

### Desarrollo y deploy
- **Local:** Vite en `:5173` con proxy `/api` → Django `:8000`.
- **Render:** comando de build `npm ci && npm run build` en `frontend/`, luego `collectstatic`. Django sirve `index.html` para cualquier ruta que no sea `/api` ni `/admin`. *(Verificar que el entorno de Render tenga Node disponible; si no, se separa el frontend como Static Site.)*

---

## 7. Cambios al modelo de datos

| Modelo | Cambio |
|--------|--------|
| `Depot` (nuevo) | Bodega: nombre, dirección, lat/lng |
| `Order` | + destinatario, teléfono, dirección, `place_id`, lat/lng, notas. `origin/destination` → `depot` + dirección |
| `Trip` → **Route** | + bodega, fecha, orden de paradas, métricas (sin optimizar vs. optimizado), algoritmo usado |
| `RouteStop` (nuevo) | ruta, pedido, `sequence`, ETA, estado (pendiente / entregado / fallido), motivo, `delivered_at` |
| `Driver` | + `user` (OneToOne) para iniciar sesión como conductor |
| `UserProfile.Role` | `admin`, `dispatcher`, `driver` |
| `DriverLocation` (nuevo, *should*) | conductor, lat/lng, timestamp — para el monitoreo en vivo |
| `DistanceCache` (nuevo) | Pares origen-destino → km/min, para no pagar dos veces a Google |

`Department` y `RouteConnection` se quedan (históricos y para Dijkstra/A\*), pero dejan de ser el núcleo.

---

## 8. Mapa de pantallas

### Despachador / Administrador (escritorio primero)
```
┌──────────┬────────────────────────────────────────────┐
│  Logo    │  Barra superior: búsqueda · fecha · usuario │
│──────────│────────────────────────────────────────────│
│ Inicio   │                                            │
│ Pedidos  │                                            │
│ Planificar│            Contenido de la sección       │
│ Rutas    │                                            │
│ Monitoreo│                                            │
│ Flota    │                                            │
│ Reportes │                                            │
│──────────│                                            │
│ Config.  │                                            │
└──────────┴────────────────────────────────────────────┘
```

| Pantalla | Contenido clave |
|----------|-----------------|
| **Login** | Marca, formulario limpio, errores claros |
| **Inicio** | "Qué requiere atención hoy": pedidos sin asignar, rutas en curso, entregas fallidas; KPIs del día |
| **Pedidos** | Tabla con búsqueda, filtros y selección múltiple; panel lateral para crear/editar con autocompletado de dirección y mini-mapa |
| **Planificador** ⭐ | Ver §9 |
| **Rutas** | Lista por fecha/estado → **detalle de ruta**: mapa, paradas en orden, línea de tiempo, métricas, acciones |
| **Monitoreo** | Mapa a pantalla completa con todas las rutas en curso, posición del conductor y % de avance |
| **Flota** | Pestañas Vehículos / Conductores; tarjetas o tabla, panel lateral para editar |
| **Reportes** | km ahorrados por optimización, entregas por día, tasa de éxito, costo por ruta |
| **Configuración** | Usuarios y roles, bodegas, precio de combustible, parámetros del optimizador |

### Conductor (móvil primero)
```
┌─────────────────────┐   ┌─────────────────────┐   ┌─────────────────────┐
│ Hola, Juan  🚚 C-123│   │ ← Parada 3 de 12    │   │ ✔ Ruta completada   │
│ Ruta de hoy · 12 par│   │ María López         │   │ 12/12 entregas      │
│ [ mini mapa ]       │   │ 5a Av 10-20, Zona 1 │   │ 48.3 km · 3h 10m    │
│ ● 1 Zona 4   ✔      │   │ 📞 Llamar           │   │                     │
│ ● 2 Zona 9   ✔      │   │ 🧭 Navegar          │   │ [ Volver al inicio ]│
│ ● 3 Zona 1  ← sig.  │   │ [✔ Entregado]       │   │                     │
│ ...                 │   │ [✖ No entregado]    │   │                     │
│ [ Iniciar ruta ]    │   │                     │   │                     │
└─────────────────────┘   └─────────────────────┘   └─────────────────────┘
   Mi ruta de hoy            Detalle de parada         Resumen del día
```
Navegación inferior: **Hoy · Historial · Perfil**.

---

## 9. Flujo estrella: planificar rutas

1. **Elegir** fecha y bodega.
2. **Pedidos:** el mapa muestra todos los pendientes como pines; la lista lateral permite filtrar y seleccionar (todos por defecto).
3. **Vehículos:** se marcan los disponibles; se ve la capacidad total contra el peso total (barra de progreso).
4. **Optimizar** → aparece un estado de carga ("Calculando matriz de distancias… Optimizando…").
5. **Resultado:**
   - Una ruta de color por vehículo en el mapa, con paradas numeradas.
   - Tarjeta por ruta: paradas, km, tiempo, carga (% de capacidad), costo.
   - **Tarjeta de comparación:** sin optimizar vs. optimizado, con **"Ahorraste X km (Y %)"**.
   - *(Could)* arrastrar paradas entre rutas.
6. **Confirmar y asignar** conductores → las rutas quedan *planificadas* y le aparecen al conductor.

Estados a diseñar: sin pedidos pendientes, capacidad insuficiente, dirección sin coordenadas, error de Google, pedido que no cabe en ningún vehículo.

---

## 10. Sistema de diseño

**Principios:** claridad antes que decoración · el mapa es protagonista · una acción principal por pantalla · todo estado tiene diseño (vacío, cargando, error, éxito).

- **Tokens:** colores (primario de marca, neutros, semánticos éxito/alerta/error/info), espaciado en escala de 4 px, radios, sombras, tipografía (Inter o Geist), modo claro y oscuro.
- **Colores de estado** (se usan igual en todo el sistema):
  pendiente = gris · planificado = azul · en curso = ámbar · entregado/completado = verde · fallido/cancelado = rojo.
- **Paleta de rutas:** 8 colores distinguibles en el mapa, también para personas con daltonismo.
- **Componentes:** botón, input, select, combobox de dirección, badge de estado, tabla con filtros, panel lateral, modal, toast, tarjeta KPI, stepper, *skeleton*, estado vacío, marcador de mapa numerado.
- **Accesibilidad:** contraste AA, navegación por teclado y *focus* visible, objetivos táctiles ≥ 44 px en la vista del conductor.
- **Responsive:** despachador desde 1280 px (usable en tablet); conductor desde 360 px.

---

## 11. Cronograma (3 semanas)

### Semana 1 — Fundaciones
| Día | Entregable |
|-----|-----------|
| 1 | Elegir nombre · logo y paleta · cerrar este plan |
| 2 | Prototipo navegable de: Planificador, Pedidos y Vista del conductor (para validar antes de programar) |
| 3 | Backend: nuevos modelos + migraciones + datos de demo (bodega y ~50 direcciones reales en Guatemala) |
| 4 | Backend: matriz de distancias (Google + caché + respaldo Haversine) |
| 5 | Backend: Clarke-Wright + 2-opt + endpoint `POST /api/routes/optimize` + pruebas unitarias |

### Semana 2 — Aplicación React
| Día | Entregable |
|-----|-----------|
| 6 | Proyecto Vite, Tailwind, shadcn, *layout* (sidebar, topbar), login y ruteo por rol |
| 7 | Pedidos: tabla, filtros, crear/editar con autocompletado de dirección |
| 8–9 | **Planificador** completo con mapa, resultado y comparación |
| 10 | Rutas: lista + detalle + acciones del ciclo de vida |

### Semana 3 — Conductor, monitoreo y pulido
| Día | Entregable |
|-----|-----------|
| 11 | Vista del conductor: ruta del día, detalle de parada, marcar entregas |
| 12 | Monitoreo en vivo + GPS del conductor |
| 13 | Inicio (KPIs) + Reportes + Flota + Configuración |
| 14 | Responsive, accesibilidad, estados vacíos/error, modo oscuro |
| 15 | Deploy en Render, guion de demo, benchmark final del algoritmo, README |

> Regla: si un día se atrasa, se recorta de **Could/Should**, nunca de **Must**.

---

## 12. Riesgos

| Riesgo | Impacto | Mitigación |
|--------|---------|------------|
| Costo o cuota de Google (la matriz crece como N²) | Alto | Caché en BD, Haversine como respaldo, límite de N en la demo, alertas de presupuesto en Google Cloud |
| API key expuesta en el frontend | Medio | Restringir la key por **HTTP referrer** y por API; usar una key separada para el servidor |
| Deploy con Node en Render | Medio | Probar el deploy el día 6, no el 15 |
| Alcance demasiado grande | Alto | MoSCoW estricto, *Must* primero |
| GPS en el navegador requiere HTTPS y permiso | Bajo | Render ya usa HTTPS; si se niega el permiso, se usa la simulación |
| Migrar datos viejos | Bajo | Los datos actuales son de demo: se regeneran con `seed_demo_data` |

---

## 13. Pendientes que conviene decidir

- [ ] **Nombre** final (§2).
- [ ] ¿Un solo tamaño de flota en la demo o varios tipos de vehículo (moto, pickup, camión)? Afecta la capacidad y el costo.
- [ ] ¿Qué ciudad o zona usar para la demo? Se sugiere Ciudad de Guatemala y alrededores.
- [ ] Título y objetivos formales de la tesis: alinear con "optimización multi-parada (CVRP) con heurísticas". Si el título menciona **IA**, enmarcar 2-opt / Recocido Simulado como técnicas de búsqueda heurística de IA.
- [ ] ¿El asesor pide métricas o formato específicos para la comparación de algoritmos?

---

## 14. Definición de "terminado" para la defensa

- Un despachador crea pedidos con direcciones reales, optimiza y ve **cuánto se ahorró**.
- Un conductor inicia sesión en su celular, ve su ruta en orden y marca entregas.
- El despachador ve ese avance en vivo.
- Hay una tabla y gráfica de *benchmark* del algoritmo lista para el documento.
- El sistema está desplegado en Render con datos de demo coherentes.
