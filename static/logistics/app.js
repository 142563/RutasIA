const API = {
    me: "/api/me/",
    users: "/api/users/",
    dashboard: "/api/dashboard/",
    departments: "/api/departments/",
    connections: "/api/connections/",
    drivers: "/api/drivers/",
    vehicles: "/api/vehicles/",
    orders: "/api/orders/",
    trips: "/api/trips/",
    planTrip: "/api/trips/plan/"
};

const state = {
    currentUser: null,
    dashboard: null,
    departments: [],
    connections: [],
    drivers: [],
    vehicles: [],
    orders: [],
    trips: [],
    users: []
};

let map = null;
let mapReady = false;
let mapHasAutoFit = false;
let activePopup = null;

const MAP_IDS = {
    connectionsSource: "connections-source",
    connectionsCasingLayer: "connections-casing-layer",
    connectionsLayer: "connections-layer",
    departmentsSource: "departments-source",
    departmentsLayer: "departments-layer",
    departmentLabelsLayer: "departments-labels-layer",
    highlightSource: "highlight-source",
    highlightLineGlowLayer: "highlight-line-glow-layer",
    highlightLineLayer: "highlight-line-layer",
    highlightPointLayer: "highlight-point-layer"
};

document.addEventListener("DOMContentLoaded", async () => {
    bindTabs();
    bindForms();
    bindFilters();
    await reloadAll();
});

function bindTabs() {
    const tabs = Array.from(document.querySelectorAll(".tab"));
    tabs.forEach((tab) => {
        tab.addEventListener("click", () => {
            tabs.forEach((x) => x.classList.remove("is-active"));
            tab.classList.add("is-active");
            const target = tab.dataset.tab;
            document.querySelectorAll(".panel").forEach((panel) => {
                panel.classList.toggle("is-active", panel.id === `tab-${target}`);
            });
            if (target === "map") {
                window.setTimeout(() => {
                    if (map) map.resize();
                }, 80);
            }
        });
    });
}

function bindForms() {
    document.getElementById("vehicle-form").addEventListener("submit", onVehicleSubmit);
    document.getElementById("driver-form").addEventListener("submit", onDriverSubmit);
    document.getElementById("order-form").addEventListener("submit", onOrderSubmit);
    document.getElementById("planner-form").addEventListener("submit", onPlannerSubmit);
    document.getElementById("event-form").addEventListener("submit", onEventSubmit);
    document.getElementById("trips-body").addEventListener("click", onTripsActionClick);
    document.getElementById("user-form").addEventListener("submit", onUserSubmit);
    document.getElementById("map-trip-select").addEventListener("change", onMapTripSelect);
}

function bindFilters() {
    document.getElementById("dash-filter-btn").addEventListener("click", reloadDashboard);
    document.getElementById("dash-clear-btn").addEventListener("click", () => {
        document.getElementById("dash-date-from").value = "";
        document.getElementById("dash-date-to").value = "";
        reloadDashboard();
    });
    ["order-filter-status", "order-filter-origin", "order-filter-dest"].forEach((id) => {
        document.getElementById(id).addEventListener("change", renderOrdersFiltered);
    });
    ["trip-filter-status", "trip-filter-vehicle", "trip-filter-from", "trip-filter-to"].forEach((id) => {
        document.getElementById(id).addEventListener("change", renderTripsFiltered);
    });
}

async function reloadAll() {
    try {
        const [meRes, deptRes, connRes, driverRes, vehicleRes, orderRes, tripRes] = await Promise.all([
            getJson(API.me),
            getJson(API.departments),
            getJson(API.connections),
            getJson(API.drivers),
            getJson(API.vehicles),
            getJson(API.orders),
            getJson(API.trips)
        ]);
        state.currentUser = meRes.user;
        state.departments = deptRes.departments;
        state.connections = connRes.connections;
        state.drivers = driverRes.drivers;
        state.vehicles = vehicleRes.vehicles;
        state.orders = orderRes.orders;
        state.trips = tripRes.trips;

        await reloadDashboard();

        if (state.currentUser && state.currentUser.role === "admin") {
            try {
                const usersRes = await getJson(API.users);
                state.users = usersRes.users;
            } catch (_) {}
        }

        renderAll();
    } catch (error) {
        showToast(error.message, true);
    }
}

async function reloadDashboard() {
    try {
        const from = document.getElementById("dash-date-from").value;
        const to = document.getElementById("dash-date-to").value;
        let url = API.dashboard;
        const params = [];
        if (from) params.push(`date_from=${from}`);
        if (to) params.push(`date_to=${to}`);
        if (params.length) url += "?" + params.join("&");
        const res = await getJson(url);
        state.dashboard = res.dashboard;
        renderDashboard();
    } catch (error) {
        showToast(error.message, true);
    }
}

function renderAll() {
    renderUserInfo();
    renderDashboard();
    renderDepartmentsInSelects();
    renderDriverSelects();
    renderVehicles();
    renderDrivers();
    renderOrdersFiltered();
    renderPlannerInputs();
    renderTripsFiltered();
    renderEventTripSelect();
    renderTripFilterVehicles();
    renderMap();
    renderUsers();
}

function renderUserInfo() {
    const user = state.currentUser;
    if (!user) return;
    document.getElementById("user-name").textContent = user.full_name || user.username;
    const badge = document.getElementById("user-badge");
    const roleLabels = { admin: "Admin", supervisor: "Supervisor", operator: "Operador" };
    badge.textContent = roleLabels[user.role] || user.role;
    badge.className = `role-badge role-${user.role}`;

    const isAdmin = user.role === "admin";
    const isSupervisor = user.role === "supervisor" || isAdmin;

    document.getElementById("tab-users-btn").style.display = isAdmin ? "" : "none";
    document.getElementById("vehicle-form-card").style.display = isSupervisor ? "" : "none";
    document.getElementById("driver-form-card").style.display = isSupervisor ? "" : "none";
    document.getElementById("order-form-card").style.display = isSupervisor ? "" : "none";
}

function renderDashboard() {
    const dashboard = state.dashboard;
    if (!dashboard) return;

    const summary = dashboard.summary;
    setText("metric-total-trips", summary.total_trips);
    setText("metric-active-trips", summary.active_trips);
    setText("metric-pending-orders", summary.pending_orders);
    setText("metric-delivered-orders", summary.delivered_orders);
    setText("metric-total-cost", summary.total_cost.toFixed(2));
    setText("metric-total-distance", summary.total_distance_km.toFixed(2));

    const statusLabels = dashboard.status_distribution.map((item) => item.status);
    const statusValues = dashboard.status_distribution.map((item) => item.total);
    drawBarChart("status-chart", statusLabels, statusValues, "#f97316");

    const timelineLabels = dashboard.timeline.map((item) => item.date.slice(5));
    const timelineValues = dashboard.timeline.map((item) => item.trips);
    drawBarChart("timeline-chart", timelineLabels, timelineValues, "#0ea5a4");

    const body = document.getElementById("vehicle-activity-body");
    body.innerHTML = "";
    if (!dashboard.vehicle_activity.length) {
        body.innerHTML = `<tr><td colspan="2">No hay actividad registrada.</td></tr>`;
        return;
    }
    dashboard.vehicle_activity.forEach((item) => {
        body.insertAdjacentHTML(
            "beforeend",
            `<tr><td>${escapeHtml(item.plate)}</td><td>${item.total_trips}</td></tr>`
        );
    });
}

function renderDepartmentsInSelects() {
    const departmentOptions = [
        `<option value="">Seleccione...</option>`,
        ...state.departments.map(
            (d) => `<option value="${d.id}">${escapeHtml(d.name)} (${escapeHtml(d.code)})</option>`
        )
    ].join("");

    ["vehicle-current-department", "order-origin", "order-destination"].forEach((id) => {
        const select = document.getElementById(id);
        if (!select) return;
        if (select.dataset.loaded === "1") {
            const previous = select.value;
            select.innerHTML = departmentOptions;
            if (previous) select.value = previous;
        } else {
            select.innerHTML = departmentOptions;
            select.dataset.loaded = "1";
        }
    });

    const filterOpts = [
        `<option value="">Todos</option>`,
        ...state.departments.map((d) => `<option value="${d.id}">${escapeHtml(d.name)}</option>`)
    ].join("");
    document.getElementById("order-filter-origin").innerHTML = filterOpts;
    document.getElementById("order-filter-dest").innerHTML = filterOpts;
}

function renderDriverSelects() {
    const activeDrivers = state.drivers.filter((d) => d.is_active);
    const opts = [
        `<option value="">Sin conductor</option>`,
        ...activeDrivers.map((d) => `<option value="${d.id}">${escapeHtml(d.name)} (${escapeHtml(d.license_number)})</option>`)
    ].join("");
    document.getElementById("vehicle-driver").innerHTML = opts;
    document.getElementById("planner-driver").innerHTML = [
        `<option value="">Sin conductor asignado</option>`,
        ...activeDrivers.map((d) => `<option value="${d.id}">${escapeHtml(d.name)}</option>`)
    ].join("");
}

function renderVehicles() {
    const body = document.getElementById("vehicles-body");
    body.innerHTML = "";
    if (!state.vehicles.length) {
        body.innerHTML = `<tr><td colspan="8">No hay vehículos registrados.</td></tr>`;
        return;
    }
    state.vehicles.forEach((v) => {
        body.insertAdjacentHTML(
            "beforeend",
            `<tr>
                <td>${escapeHtml(v.plate)}</td>
                <td>${escapeHtml(v.model)}</td>
                <td>${v.capacity_kg.toFixed(2)} kg</td>
                <td>${v.fuel_efficiency_km_l.toFixed(2)} km/l</td>
                <td>Q ${v.cost_per_km.toFixed(2)}</td>
                <td>${escapeHtml(v.driver_name || "-")}</td>
                <td>${escapeHtml(v.current_department_name || "-")}</td>
                <td>${statusChip(v.is_active ? "active" : "inactive")}</td>
            </tr>`
        );
    });
}

function renderDrivers() {
    const body = document.getElementById("drivers-body");
    body.innerHTML = "";
    if (!state.drivers.length) {
        body.innerHTML = `<tr><td colspan="4">No hay conductores registrados.</td></tr>`;
        return;
    }
    state.drivers.forEach((d) => {
        body.insertAdjacentHTML(
            "beforeend",
            `<tr>
                <td>${escapeHtml(d.name)}</td>
                <td>${escapeHtml(d.phone || "-")}</td>
                <td>${escapeHtml(d.license_number)}</td>
                <td>${statusChip(d.is_active ? "active" : "inactive")}</td>
            </tr>`
        );
    });
}

function renderOrdersFiltered() {
    const statusVal = document.getElementById("order-filter-status").value;
    const originVal = document.getElementById("order-filter-origin").value;
    const destVal = document.getElementById("order-filter-dest").value;

    const filtered = state.orders.filter((o) => {
        if (statusVal && o.status !== statusVal) return false;
        if (originVal && String(o.origin_id) !== originVal) return false;
        if (destVal && String(o.destination_id) !== destVal) return false;
        return true;
    });

    const body = document.getElementById("orders-body");
    body.innerHTML = "";
    if (!filtered.length) {
        body.innerHTML = `<tr><td colspan="7">No hay pedidos con estos filtros.</td></tr>`;
        return;
    }
    filtered.forEach((o) => {
        body.insertAdjacentHTML(
            "beforeend",
            `<tr>
                <td>${escapeHtml(o.code)}</td>
                <td>${escapeHtml(o.origin_name)}</td>
                <td>${escapeHtml(o.destination_name)}</td>
                <td>${o.weight_kg.toFixed(2)} kg</td>
                <td>${o.package_count}</td>
                <td>${priorityLabel(o.priority)}</td>
                <td>${statusChip(o.status)}</td>
            </tr>`
        );
    });
}

function renderPlannerInputs() {
    const vehicleSelect = document.getElementById("planner-vehicle");
    const activeVehicles = state.vehicles.filter((v) => v.is_active);
    vehicleSelect.innerHTML = [
        `<option value="">Seleccione un vehículo...</option>`,
        ...activeVehicles.map((v) => `<option value="${v.id}">${escapeHtml(v.plate)} - ${escapeHtml(v.model)}</option>`)
    ].join("");

    const pendingOrders = state.orders.filter((o) => o.status === "pending");
    const checklist = document.getElementById("planner-orders-list");
    checklist.innerHTML = "";
    if (!pendingOrders.length) {
        checklist.innerHTML = `<p>No hay pedidos pendientes.</p>`;
        return;
    }
    pendingOrders.forEach((order) => {
        checklist.insertAdjacentHTML(
            "beforeend",
            `<label class="check-item">
                <input type="checkbox" value="${order.id}" name="order_ids">
                <span>
                    <strong>${escapeHtml(order.code)}</strong> ${escapeHtml(order.origin_name)} -> ${escapeHtml(order.destination_name)}
                    <br>
                    <small>${order.weight_kg.toFixed(2)} kg | ${order.package_count} productos | prioridad ${priorityLabel(order.priority)}</small>
                </span>
            </label>`
        );
    });
}

function renderTripFilterVehicles() {
    const sel = document.getElementById("trip-filter-vehicle");
    sel.innerHTML = [
        `<option value="">Todos</option>`,
        ...state.vehicles.map((v) => `<option value="${v.id}">${escapeHtml(v.plate)}</option>`)
    ].join("");
}

function renderTripsFiltered() {
    const statusVal = document.getElementById("trip-filter-status").value;
    const vehicleVal = document.getElementById("trip-filter-vehicle").value;
    const fromVal = document.getElementById("trip-filter-from").value;
    const toVal = document.getElementById("trip-filter-to").value;

    const filtered = state.trips.filter((t) => {
        if (statusVal && t.status !== statusVal) return false;
        if (vehicleVal && String(t.vehicle_id) !== vehicleVal) return false;
        if (fromVal && t.started_at && t.started_at.slice(0, 10) < fromVal) return false;
        if (toVal && t.started_at && t.started_at.slice(0, 10) > toVal) return false;
        return true;
    });

    const body = document.getElementById("trips-body");
    body.innerHTML = "";
    if (!filtered.length) {
        body.innerHTML = `<tr><td colspan="9">No hay viajes con estos filtros.</td></tr>`;
        return;
    }
    filtered.forEach((trip) => {
        body.insertAdjacentHTML(
            "beforeend",
            `<tr>
                <td>${escapeHtml(trip.code)}</td>
                <td>${escapeHtml(trip.vehicle_plate)}</td>
                <td>${escapeHtml(trip.driver_name || "-")}</td>
                <td>${escapeHtml(trip.route_nodes.join(" → "))}</td>
                <td>${trip.total_distance_km.toFixed(2)} km</td>
                <td>${trip.estimated_fuel_liters.toFixed(2)} l</td>
                <td>Q ${trip.estimated_cost.toFixed(2)}</td>
                <td>${statusChip(trip.status)}</td>
                <td>${buildTripActions(trip)}</td>
            </tr>`
        );
    });
}

function renderEventTripSelect() {
    const select = document.getElementById("event-trip-id");
    select.innerHTML = [
        `<option value="">Seleccione...</option>`,
        ...state.trips.map((trip) => `<option value="${trip.id}">${escapeHtml(trip.code)} (${statusLabel(trip.status)})</option>`)
    ].join("");
}

function renderMapTripSelect() {
    const sel = document.getElementById("map-trip-select");
    sel.innerHTML = [
        `<option value="">Ninguno</option>`,
        ...state.trips.map((t) => `<option value="${t.id}">${escapeHtml(t.code)} — ${escapeHtml(t.route_nodes.join(" → "))}</option>`)
    ].join("");
}

function renderUsers() {
    const body = document.getElementById("users-body");
    if (!body) return;
    body.innerHTML = "";
    if (!state.users.length) {
        body.innerHTML = `<tr><td colspan="5">No hay usuarios registrados.</td></tr>`;
        return;
    }
    const roleLabels = { admin: "Administrador", supervisor: "Supervisor", operator: "Operador" };
    state.users.forEach((u) => {
        body.insertAdjacentHTML(
            "beforeend",
            `<tr>
                <td>${escapeHtml(u.username)}</td>
                <td>${escapeHtml(u.full_name || "-")}</td>
                <td>${escapeHtml(u.email || "-")}</td>
                <td><span class="role-badge role-${u.role}">${roleLabels[u.role] || u.role}</span></td>
                <td>${statusChip(u.is_active ? "active" : "inactive")}</td>
            </tr>`
        );
    });
}

// ── MAP ──────────────────────────────────────────────────────────────────────

function renderMap() {
    const depts = state.departments.filter((d) => d.latitude && d.longitude);
    if (!depts.length) return;

    if (!map) {
        map = new maplibregl.Map({
            container: "route-map",
            style: {
                version: 8,
                sources: {
                    satellite: {
                        type: "raster",
                        tiles: [
                            "https://services.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}"
                        ],
                        tileSize: 256,
                        attribution: "Tiles &copy; Esri"
                    },
                    satellite_labels: {
                        type: "raster",
                        tiles: [
                            "https://services.arcgisonline.com/ArcGIS/rest/services/Reference/World_Boundaries_and_Places/MapServer/tile/{z}/{y}/{x}"
                        ],
                        tileSize: 256,
                        attribution: "Labels &copy; Esri"
                    }
                },
                layers: [
                    {
                        id: "satellite-base",
                        type: "raster",
                        source: "satellite"
                    },
                    {
                        id: "satellite-labels",
                        type: "raster",
                        source: "satellite_labels"
                    }
                ]
            },
            center: [-90.3, 15.45],
            zoom: 7
        });

        map.addControl(new maplibregl.NavigationControl(), "top-right");
        map.on("load", () => {
            mapReady = true;
            ensureMapLayers();
            updateMapData();
            bindMapEvents();
        });
    }

    renderMapTripSelect();
    if (mapReady) updateMapData();
}

function onMapTripSelect(event) {
    if (!mapReady) return;
    const tripId = Number(event.target.value);
    if (!tripId) {
        clearHighlightedRoute();
        return;
    }

    const trip = state.trips.find((t) => t.id === tripId);
    if (!trip) return;

    const coords = trip.route_nodes.map((name) => {
        const dept = state.departments.find((d) => d.name === name);
        return dept && dept.latitude ? [Number(dept.longitude), Number(dept.latitude)] : null;
    }).filter(Boolean);

    if (coords.length < 2) {
        clearHighlightedRoute();
        return;
    }

    const highlight = buildHighlightGeoJson(trip, coords);
    const source = map.getSource(MAP_IDS.highlightSource);
    if (source) {
        source.setData(highlight);
    }

    const bounds = coords.reduce(
        (acc, coord) => acc.extend(coord),
        new maplibregl.LngLatBounds(coords[0], coords[0])
    );
    map.fitBounds(bounds, { padding: 36, duration: 500, maxZoom: 10 });
}

function ensureMapLayers() {
    if (!map.getSource(MAP_IDS.connectionsSource)) {
        map.addSource(MAP_IDS.connectionsSource, {
            type: "geojson",
            data: emptyFeatureCollection()
        });
        map.addLayer({
            id: MAP_IDS.connectionsCasingLayer,
            type: "line",
            source: MAP_IDS.connectionsSource,
            paint: {
                "line-color": "rgba(15, 23, 42, 0.24)",
                "line-width": [
                    "interpolate",
                    ["linear"],
                    ["zoom"],
                    5,
                    1.8,
                    9,
                    3.2,
                    12,
                    5.2
                ],
                "line-opacity": 0.5
            }
        });
        map.addLayer({
            id: MAP_IDS.connectionsLayer,
            type: "line",
            source: MAP_IDS.connectionsSource,
            paint: {
                "line-color": "#14b8a6",
                "line-width": [
                    "interpolate",
                    ["linear"],
                    ["zoom"],
                    5,
                    1.1,
                    9,
                    2.1,
                    12,
                    3.3
                ],
                "line-opacity": 0.72
            }
        });
    }

    if (!map.getSource(MAP_IDS.departmentsSource)) {
        map.addSource(MAP_IDS.departmentsSource, {
            type: "geojson",
            data: emptyFeatureCollection()
        });
        map.addLayer({
            id: MAP_IDS.departmentsLayer,
            type: "circle",
            source: MAP_IDS.departmentsSource,
            paint: {
                "circle-radius": [
                    "interpolate",
                    ["linear"],
                    ["zoom"],
                    5,
                    5.5,
                    9,
                    7.3,
                    12,
                    9
                ],
                "circle-color": "#fb923c",
                "circle-stroke-color": "#ffffff",
                "circle-stroke-width": 2.2
            }
        });
        map.addLayer({
            id: MAP_IDS.departmentLabelsLayer,
            type: "symbol",
            source: MAP_IDS.departmentsSource,
            layout: {
                "text-field": ["get", "code"],
                "text-size": [
                    "interpolate",
                    ["linear"],
                    ["zoom"],
                    5,
                    10,
                    9,
                    11.5,
                    12,
                    13
                ],
                "text-offset": [0, 1.4]
            },
            paint: {
                "text-color": "#0f1f35",
                "text-halo-color": "#ffffff",
                "text-halo-width": 1.35
            }
        });
    }

    if (!map.getSource(MAP_IDS.highlightSource)) {
        map.addSource(MAP_IDS.highlightSource, {
            type: "geojson",
            data: emptyFeatureCollection()
        });
        map.addLayer({
            id: MAP_IDS.highlightLineGlowLayer,
            type: "line",
            source: MAP_IDS.highlightSource,
            filter: ["==", ["geometry-type"], "LineString"],
            paint: {
                "line-color": "rgba(249, 115, 22, 0.35)",
                "line-width": [
                    "interpolate",
                    ["linear"],
                    ["zoom"],
                    5,
                    8,
                    10,
                    11,
                    12,
                    13
                ],
                "line-opacity": 0.5,
                "line-blur": 0.85
            }
        });
        map.addLayer({
            id: MAP_IDS.highlightLineLayer,
            type: "line",
            source: MAP_IDS.highlightSource,
            filter: ["==", ["geometry-type"], "LineString"],
            paint: {
                "line-color": "#f97316",
                "line-width": [
                    "interpolate",
                    ["linear"],
                    ["zoom"],
                    5,
                    3.2,
                    10,
                    4.8,
                    12,
                    6.2
                ],
                "line-opacity": 0.9
            }
        });
        map.addLayer({
            id: MAP_IDS.highlightPointLayer,
            type: "circle",
            source: MAP_IDS.highlightSource,
            filter: ["==", ["geometry-type"], "Point"],
            paint: {
                "circle-radius": 8.5,
                "circle-color": ["coalesce", ["get", "marker_color"], "#f97316"],
                "circle-stroke-color": "#ffffff",
                "circle-stroke-width": 2
            }
        });
    }
}

function bindMapEvents() {
    map.on("click", MAP_IDS.departmentsLayer, (event) => {
        const feature = event.features && event.features[0];
        if (!feature) return;

        const coords = feature.geometry.coordinates;
        const { name, code } = feature.properties || {};
        if (activePopup) activePopup.remove();
        activePopup = new maplibregl.Popup({ closeButton: false, closeOnClick: true, offset: 10 })
            .setLngLat(coords)
            .setHTML(`<strong>${escapeHtml(name || "")}</strong><br>${escapeHtml(code || "")}`)
            .addTo(map);
    });

    [MAP_IDS.departmentsLayer, MAP_IDS.highlightPointLayer].forEach((layerId) => {
        map.on("mouseenter", layerId, () => {
            map.getCanvas().style.cursor = "pointer";
        });
        map.on("mouseleave", layerId, () => {
            map.getCanvas().style.cursor = "";
        });
    });
}

function updateMapData() {
    ensureMapLayers();

    const connectionsSource = map.getSource(MAP_IDS.connectionsSource);
    if (connectionsSource) {
        connectionsSource.setData(buildConnectionsGeoJson());
    }

    const departmentsSource = map.getSource(MAP_IDS.departmentsSource);
    if (departmentsSource) {
        departmentsSource.setData(buildDepartmentsGeoJson());
    }

    clearHighlightedRoute();
    fitMapToDepartments();
}

function clearHighlightedRoute() {
    const source = map && map.getSource(MAP_IDS.highlightSource);
    if (source) source.setData(emptyFeatureCollection());
}

function fitMapToDepartments() {
    if (mapHasAutoFit) return;

    const coords = state.departments
        .filter((department) => department.latitude && department.longitude)
        .map((department) => [Number(department.longitude), Number(department.latitude)]);

    if (coords.length < 2) return;

    const bounds = coords.reduce(
        (acc, coord) => acc.extend(coord),
        new maplibregl.LngLatBounds(coords[0], coords[0])
    );

    map.fitBounds(bounds, {
        padding: { top: 30, right: 30, bottom: 40, left: 30 },
        maxZoom: 8.6,
        duration: 450
    });
    mapHasAutoFit = true;
}

function buildConnectionsGeoJson() {
    const features = state.connections.map((connection) => {
        const origin = state.departments.find((department) => department.id === connection.origin_id);
        const destination = state.departments.find((department) => department.id === connection.destination_id);
        if (!origin || !destination || !origin.latitude || !destination.latitude) {
            return null;
        }

        return {
            type: "Feature",
            geometry: {
                type: "LineString",
                coordinates: [
                    [Number(origin.longitude), Number(origin.latitude)],
                    [Number(destination.longitude), Number(destination.latitude)]
                ]
            },
            properties: {
                distance_km: connection.distance_km
            }
        };
    }).filter(Boolean);

    return {
        type: "FeatureCollection",
        features
    };
}

function buildDepartmentsGeoJson() {
    const features = state.departments
        .filter((department) => department.latitude && department.longitude)
        .map((department) => ({
            type: "Feature",
            geometry: {
                type: "Point",
                coordinates: [Number(department.longitude), Number(department.latitude)]
            },
            properties: {
                id: department.id,
                name: department.name,
                code: department.code
            }
        }));

    return {
        type: "FeatureCollection",
        features
    };
}

function buildHighlightGeoJson(trip, coordinates) {
    const features = [
        {
            type: "Feature",
            geometry: {
                type: "LineString",
                coordinates
            },
            properties: {
                trip_id: trip.id
            }
        }
    ];

    coordinates.forEach((coordinate, index) => {
        features.push({
            type: "Feature",
            geometry: {
                type: "Point",
                coordinates: coordinate
            },
            properties: {
                marker_color: index === 0 ? "#22c55e" : index === coordinates.length - 1 ? "#ef4444" : "#f97316",
                label: trip.route_nodes[index] || ""
            }
        });
    });

    return {
        type: "FeatureCollection",
        features
    };
}

function emptyFeatureCollection() {
    return {
        type: "FeatureCollection",
        features: []
    };
}

// ── FORM HANDLERS ─────────────────────────────────────────────────────────────

async function onVehicleSubmit(event) {
    event.preventDefault();
    const form = event.currentTarget;
    const payload = {
        plate: form.plate.value.trim(),
        model: form.model.value.trim(),
        capacity_kg: Number(form.capacity_kg.value),
        fuel_efficiency_km_l: Number(form.fuel_efficiency_km_l.value),
        cost_per_km: Number(form.cost_per_km.value),
        current_department_id: form.current_department_id.value ? Number(form.current_department_id.value) : null,
        driver_id: form.driver_id.value ? Number(form.driver_id.value) : null,
        is_active: form.is_active.checked
    };
    try {
        await postJson(API.vehicles, payload);
        form.reset();
        showToast("Vehículo registrado.");
        await reloadAll();
    } catch (error) {
        showToast(error.message, true);
    }
}

async function onDriverSubmit(event) {
    event.preventDefault();
    const form = event.currentTarget;
    const payload = {
        name: form.name.value.trim(),
        phone: form.phone.value.trim(),
        license_number: form.license_number.value.trim(),
        is_active: form.is_active.checked
    };
    try {
        await postJson(API.drivers, payload);
        form.reset();
        showToast("Conductor registrado.");
        await reloadAll();
    } catch (error) {
        showToast(error.message, true);
    }
}

async function onOrderSubmit(event) {
    event.preventDefault();
    const form = event.currentTarget;
    const payload = {
        origin_id: Number(form.origin_id.value),
        destination_id: Number(form.destination_id.value),
        weight_kg: Number(form.weight_kg.value),
        package_count: Number(form.package_count.value),
        priority: form.priority.value
    };
    try {
        await postJson(API.orders, payload);
        form.reset();
        showToast("Pedido creado.");
        await reloadAll();
    } catch (error) {
        showToast(error.message, true);
    }
}

async function onPlannerSubmit(event) {
    event.preventDefault();
    const form = event.currentTarget;
    const selectedOrders = Array.from(
        document.querySelectorAll("#planner-orders-list input[name='order_ids']:checked")
    ).map((node) => Number(node.value));
    if (!selectedOrders.length) {
        showToast("Selecciona al menos un pedido.", true);
        return;
    }
    const vehicleId = Number(form.vehicle_id.value);
    if (!vehicleId) {
        showToast("Selecciona un vehículo.", true);
        return;
    }
    const driverId = form.driver_id.value ? Number(form.driver_id.value) : null;
    try {
        const response = await postJson(API.planTrip, {
            vehicle_id: vehicleId,
            driver_id: driverId,
            order_ids: selectedOrders
        });
        showPlannerResult(response.trip);
        showToast("Viaje planificado correctamente.");
        await reloadAll();
    } catch (error) {
        showToast(error.message, true);
    }
}

async function onTripsActionClick(event) {
    const button = event.target.closest("button[data-action]");
    if (!button) return;
    const tripId = Number(button.dataset.tripId);
    const action = button.dataset.action;
    try {
        await postJson(`/api/trips/${tripId}/action/`, { action });
        showToast(`Acción "${action}" ejecutada.`);
        await reloadAll();
    } catch (error) {
        showToast(error.message, true);
    }
}

async function onEventSubmit(event) {
    event.preventDefault();
    const form = event.currentTarget;
    const tripId = Number(form.trip_id.value);
    const note = form.note.value.trim();
    if (!tripId || !note) {
        showToast("Debes seleccionar viaje y escribir evento.", true);
        return;
    }
    try {
        await postJson(`/api/trips/${tripId}/events/`, { note });
        form.reset();
        showToast("Evento registrado.");
        await reloadAll();
    } catch (error) {
        showToast(error.message, true);
    }
}

async function onUserSubmit(event) {
    event.preventDefault();
    const form = event.currentTarget;
    const payload = {
        username: form.username.value.trim(),
        password: form.password.value,
        first_name: form.first_name.value.trim(),
        last_name: form.last_name.value.trim(),
        email: form.email.value.trim(),
        role: form.role.value
    };
    try {
        await postJson(API.users, payload);
        form.reset();
        showToast("Usuario creado.");
        const res = await getJson(API.users);
        state.users = res.users;
        renderUsers();
    } catch (error) {
        showToast(error.message, true);
    }
}

// ── DISPLAY ───────────────────────────────────────────────────────────────────

function showPlannerResult(trip) {
    const box = document.getElementById("planner-result");
    box.innerHTML = `
        <h3>Resultado de planificación</h3>
        <p><strong>Código:</strong> ${escapeHtml(trip.code)}</p>
        <p><strong>Vehículo:</strong> ${escapeHtml(trip.vehicle_plate)}</p>
        <p><strong>Conductor:</strong> ${escapeHtml(trip.driver_name || "No asignado")}</p>
        <p><strong>Ruta:</strong> ${escapeHtml(trip.route_nodes.join(" → "))}</p>
        <p><strong>Distancia:</strong> ${trip.total_distance_km.toFixed(2)} km</p>
        <p><strong>Combustible estimado:</strong> ${trip.estimated_fuel_liters.toFixed(2)} litros</p>
        <p><strong>Costo estimado:</strong> Q ${trip.estimated_cost.toFixed(2)}</p>
        <p><strong>Pedidos asociados:</strong> ${trip.orders.length}</p>
    `;
}

function buildTripActions(trip) {
    const role = state.currentUser ? state.currentUser.role : "operator";
    if (role === "operator") return "—";
    if (trip.status === "completed" || trip.status === "canceled") return "Sin acciones";
    if (trip.status === "planned") {
        return `
            <button class="btn-inline" data-action="start" data-trip-id="${trip.id}">Iniciar</button>
            <button class="btn-inline btn-neutral" data-action="complete" data-trip-id="${trip.id}">Completar</button>
            <button class="btn-inline btn-danger" data-action="cancel" data-trip-id="${trip.id}">Cancelar</button>
        `;
    }
    return `
        <button class="btn-inline btn-neutral" data-action="complete" data-trip-id="${trip.id}">Completar</button>
        <button class="btn-inline btn-danger" data-action="cancel" data-trip-id="${trip.id}">Cancelar</button>
    `;
}

// ── CHART ─────────────────────────────────────────────────────────────────────

function drawBarChart(canvasId, labels, values, color) {
    const canvas = document.getElementById(canvasId);
    const ctx = canvas.getContext("2d");
    const width = canvas.width;
    const height = canvas.height;
    ctx.clearRect(0, 0, width, height);

    if (!labels.length || !values.length) {
        ctx.fillStyle = "#3f5367";
        ctx.font = "14px Trebuchet MS";
        ctx.fillText("Sin datos para mostrar.", 12, 26);
        return;
    }

    const padding = { top: 20, right: 20, bottom: 58, left: 36 };
    const graphWidth = width - padding.left - padding.right;
    const graphHeight = height - padding.top - padding.bottom;
    const maxValue = Math.max(...values, 1);
    const barWidth = (graphWidth / values.length) * 0.66;

    ctx.strokeStyle = "rgba(19, 33, 58, 0.24)";
    ctx.beginPath();
    ctx.moveTo(padding.left, padding.top);
    ctx.lineTo(padding.left, padding.top + graphHeight);
    ctx.lineTo(padding.left + graphWidth, padding.top + graphHeight);
    ctx.stroke();

    values.forEach((value, index) => {
        const x = padding.left + (index * graphWidth) / values.length + (graphWidth / values.length - barWidth) / 2;
        const barHeight = (value / maxValue) * graphHeight;
        const y = padding.top + graphHeight - barHeight;

        ctx.fillStyle = color;
        ctx.fillRect(x, y, barWidth, barHeight);

        ctx.fillStyle = "#10273f";
        ctx.font = "12px Trebuchet MS";
        ctx.fillText(String(value), x, y - 6);

        const label = labels[index].replaceAll("_", " ");
        ctx.save();
        ctx.translate(x + barWidth / 2, height - 14);
        ctx.rotate(-0.42);
        ctx.textAlign = "right";
        ctx.fillStyle = "#3a5369";
        ctx.fillText(label, 0, 0);
        ctx.restore();
    });
}

// ── HTTP ──────────────────────────────────────────────────────────────────────

async function getJson(url) {
    const response = await fetch(url, { credentials: "same-origin" });
    const data = await response.json();
    if (!response.ok || !data.ok) {
        throw new Error(data.error || `Error en ${url}`);
    }
    return data;
}

async function postJson(url, payload) {
    const response = await fetch(url, {
        method: "POST",
        credentials: "same-origin",
        headers: {
            "Content-Type": "application/json",
            "X-CSRFToken": getCookie("csrftoken")
        },
        body: JSON.stringify(payload)
    });
    const data = await response.json();
    if (!response.ok || !data.ok) {
        throw new Error(data.error || `Error en ${url}`);
    }
    return data;
}

// ── HELPERS ───────────────────────────────────────────────────────────────────

function statusLabel(status) {
    const labels = {
        pending: "Pendiente", assigned: "Asignado", in_transit: "En tránsito",
        delivered: "Entregado", canceled: "Cancelado",
        planned: "Planificado", in_progress: "En progreso", completed: "Completado"
    };
    return labels[status] || status;
}

function priorityLabel(priority) {
    const labels = { low: "Baja", normal: "Normal", high: "Alta" };
    return labels[priority] || priority;
}

function statusChip(status) {
    if (status === "active") return `<span class="status-chip status-completed">Activo</span>`;
    if (status === "inactive") return `<span class="status-chip status-canceled">Inactivo</span>`;
    return `<span class="status-chip status-${status}">${escapeHtml(statusLabel(status))}</span>`;
}

function setText(id, value) {
    const node = document.getElementById(id);
    if (node) node.textContent = String(value);
}

function getCookie(name) {
    const cookies = document.cookie ? document.cookie.split(";") : [];
    for (const cookie of cookies) {
        const [rawName, ...rest] = cookie.trim().split("=");
        if (rawName === name) return decodeURIComponent(rest.join("="));
    }
    return "";
}

function showToast(message, isError = false) {
    const toast = document.getElementById("toast");
    toast.textContent = message;
    toast.style.background = isError ? "rgba(127, 29, 29, 0.96)" : "rgba(15, 23, 42, 0.95)";
    toast.classList.add("show");
    window.setTimeout(() => toast.classList.remove("show"), 2400);
}

function escapeHtml(value) {
    return String(value)
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;")
        .replaceAll('"', "&quot;")
        .replaceAll("'", "&#039;");
}
