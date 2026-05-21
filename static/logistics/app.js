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
    planTrip: "/api/trips/plan/",
    fuelPrice: "/api/fuel-price/"
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
let mapHasAutoFit = false;
let activeInfoWindow = null;
let selectedMapTripId = null;
let gmapMarkers = [];
let gmapConnections = [];
let gmapRoutePolyline = null;
let gmapRouteMarkers = [];

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
                    if (map) google.maps.event.trigger(map, "resize");
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
    document.getElementById("department-form").addEventListener("submit", onDepartmentSubmit);
    document.getElementById("map-trip-select").addEventListener("change", onMapTripSelect);
    document.getElementById("fuel-form").addEventListener("submit", onFuelPriceSubmit);
    document.getElementById("btn-edit-fuel").addEventListener("click", () => {
        document.getElementById("fuel-form").style.display = "";
        document.getElementById("btn-edit-fuel").style.display = "none";
    });
    document.getElementById("btn-cancel-fuel").addEventListener("click", () => {
        document.getElementById("fuel-form").style.display = "none";
        document.getElementById("btn-edit-fuel").style.display = "";
    });
}


// â”€â”€ PRECIO DE GASOLINA â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

async function reloadFuelPrice() {
    try {
        const res = await getJson(API.fuelPrice);
        renderFuelPrice(res.fuel_price);
    } catch (_) {}
}

function renderFuelPrice(fp) {
    if (!fp) return;
    document.getElementById("fuel-regular").textContent = `Q ${fp.regular_gtq_gal.toFixed(2)}/gal`;
    document.getElementById("fuel-super").textContent = `Q ${fp.super_gtq_gal.toFixed(2)}/gal`;
    document.getElementById("fuel-diesel").textContent = `Q ${fp.diesel_gtq_gal.toFixed(2)}/gal`;
    const d = new Date(fp.updated_at);
    document.getElementById("fuel-updated-at").textContent =
        `${fp.source} Â· actualizado ${d.toLocaleDateString("es-GT")} ${d.toLocaleTimeString("es-GT", { hour: "2-digit", minute: "2-digit" })}`;
    const isAdmin = state.currentUser && state.currentUser.role === "admin";
    document.getElementById("btn-edit-fuel").style.display = isAdmin ? "" : "none";
    const form = document.getElementById("fuel-form");
    form.regular_gtq_gal.value = fp.regular_gtq_gal.toFixed(2);
    form.super_gtq_gal.value = fp.super_gtq_gal.toFixed(2);
    form.diesel_gtq_gal.value = fp.diesel_gtq_gal.toFixed(2);
    form.source.value = fp.source;
}

async function onFuelPriceSubmit(event) {
    event.preventDefault();
    const form = event.currentTarget;
    try {
        const res = await postJson(API.fuelPrice, {
            regular_gtq_gal: Number(form.regular_gtq_gal.value),
            super_gtq_gal: Number(form.super_gtq_gal.value),
            diesel_gtq_gal: Number(form.diesel_gtq_gal.value),
            source: form.source.value || "Manual"
        });
        renderFuelPrice(res.fuel_price);
        form.style.display = "none";
        document.getElementById("btn-edit-fuel").style.display = "";
        showToast("Precio de combustible actualizado.");
    } catch (error) {
        showToast(error.message, true);
    }
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

        await Promise.all([reloadDashboard(), reloadFuelPrice()]);

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
    renderDepartments();
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
    document.getElementById("tab-departments-btn").style.display = isSupervisor ? "" : "none";
    document.getElementById("vehicle-form-card").style.display = isSupervisor ? "" : "none";
    document.getElementById("driver-form-card").style.display = isSupervisor ? "" : "none";
    document.getElementById("order-form-card").style.display = isSupervisor ? "" : "none";
    document.getElementById("department-form-card").style.display = isSupervisor ? "" : "none";
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

function renderDepartments() {
    const body = document.getElementById("departments-body");
    if (!body) return;
    body.innerHTML = "";
    if (!state.departments.length) {
        body.innerHTML = `<tr><td colspan="4">No hay departamentos registrados.</td></tr>`;
        return;
    }
    state.departments.forEach((d) => {
        body.insertAdjacentHTML(
            "beforeend",
            `<tr>
                <td>${escapeHtml(d.code)}</td>
                <td>${escapeHtml(d.name)}</td>
                <td>${d.latitude !== null && d.latitude !== undefined ? d.latitude : "-"}</td>
                <td>${d.longitude !== null && d.longitude !== undefined ? d.longitude : "-"}</td>
            </tr>`
        );
    });
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
        body.innerHTML = `<tr><td colspan="8">No hay vehÃ­culos registrados.</td></tr>`;
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
        `<option value="">Seleccione un vehÃ­culo...</option>`,
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
                <td>${escapeHtml(trip.route_nodes.join(" â†’ "))}</td>
                <td>${trip.total_distance_km.toFixed(2)} km</td>
                <td>${trip.estimated_fuel_gallons.toFixed(2)} gal</td>
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
    const previousSelection = selectedMapTripId || Number(sel.value || 0);
    sel.innerHTML = [
        `<option value="">Ninguno</option>`,
        ...state.trips.map((trip) => `<option value="${trip.id}">${escapeHtml(trip.code)} - ${escapeHtml(trip.route_nodes.join(" -> "))}</option>`)
    ].join("");

    if (previousSelection && state.trips.some((trip) => trip.id === previousSelection)) {
        sel.value = String(previousSelection);
        selectedMapTripId = previousSelection;
    } else {
        sel.value = "";
        selectedMapTripId = null;
    }
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

// â”€â”€ MAP â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

function renderMap() {
    const depts = state.departments.filter((d) => d.latitude && d.longitude);
    if (!depts.length) return;

    if (!map) {
        map = new google.maps.Map(document.getElementById("route-map"), {
            center: { lat: 15.45, lng: -90.3 },
            zoom: 7,
            mapTypeId: "hybrid",
            streetViewControl: false,
            rotateControl: false
        });
    }

    renderMapTripSelect();
    updateMapData();
}

function onMapTripSelect(event) {
    const tripId = Number(event.target.value || 0);
    focusMapTripById(tripId, { shouldFit: true });
}

async function fetchRoadGeometry(waypointCoords) {
    if (window.ORS_API_KEY) {
        try {
            return await _fetchViaORS(waypointCoords);
        } catch (err) {
            console.warn("ORS no disponible, usando OSRM:", err.message);
        }
    }
    return _fetchViaOSRM(waypointCoords);
}

async function _fetchViaORS(waypointCoords) {
    const resp = await fetch("https://api.openrouteservice.org/v2/directions/driving-car/geojson", {
        method: "POST",
        headers: {
            "Content-Type": "application/json",
            "Authorization": "Bearer " + window.ORS_API_KEY
        },
        body: JSON.stringify({
            coordinates: waypointCoords,
            preference: "fastest",
            geometry_simplify: false
        })
    });
    if (!resp.ok) {
        const msg = await resp.text().catch(() => resp.status);
        throw new Error(`ORS ${resp.status}: ${msg}`);
    }
    const data = await resp.json();
    if (!data.features?.[0]) throw new Error("ORS sin geometrÃ­a");
    return data.features[0].geometry.coordinates;
}

async function _fetchViaOSRM(waypointCoords) {
    const coordStr = waypointCoords.map(([lon, lat]) => `${lon},${lat}`).join(";");
    const url = `https://router.project-osrm.org/route/v1/driving/${coordStr}?overview=full&geometries=geojson`;
    const resp = await fetch(url);
    if (!resp.ok) throw new Error(`OSRM ${resp.status}`);
    const data = await resp.json();
    if (data.code !== "Ok" || !data.routes?.[0]) throw new Error("Sin ruta OSRM");
    return data.routes[0].geometry.coordinates;
}

async function focusMapTripById(tripId, options = {}) {
    const { shouldFit = true } = options;

    if (!tripId) {
        selectedMapTripId = null;
        clearHighlightedRoute();
        updateMapRouteSummary(null);
        return;
    }

    const trip = state.trips.find((t) => t.id === tripId);
    if (!trip) {
        selectedMapTripId = null;
        clearHighlightedRoute();
        updateMapRouteSummary(null);
        return;
    }

    const waypointCoords = trip.route_nodes
        .map((name) => {
            const dept = state.departments.find((d) => d.name === name);
            return dept && dept.latitude ? [Number(dept.longitude), Number(dept.latitude)] : null;
        })
        .filter(Boolean);

    if (waypointCoords.length < 2) {
        selectedMapTripId = null;
        clearHighlightedRoute();
        updateMapRouteSummary(null);
        return;
    }

    selectedMapTripId = tripId;
    updateMapRouteSummary(trip);

    const drawRoute = (coords) => {
        clearHighlightedRoute();
        gmapRoutePolyline = new google.maps.Polyline({
            path: coords.map(([lng, lat]) => ({ lat, lng })),
            strokeColor: "#ff7f11",
            strokeOpacity: 0.96,
            strokeWeight: 5,
            zIndex: 10,
            map
        });
        waypointCoords.forEach(([lng, lat], index) => {
            const isFirst = index === 0;
            const isLast = index === waypointCoords.length - 1;
            const color = isFirst ? "#22c55e" : isLast ? "#ef4444" : "#f59e0b";
            const marker = new google.maps.Marker({
                position: { lat, lng },
                map,
                title: trip.route_nodes[index] || "",
                icon: {
                    path: google.maps.SymbolPath.CIRCLE,
                    scale: isFirst || isLast ? 10 : 7,
                    fillColor: color,
                    fillOpacity: 1,
                    strokeColor: "#ffffff",
                    strokeWeight: 2.5
                },
                zIndex: 20
            });
            gmapRouteMarkers.push(marker);
        });
        if (shouldFit) {
            const bounds = new google.maps.LatLngBounds();
            coords.forEach(([lng, lat]) => bounds.extend({ lat, lng }));
            map.fitBounds(bounds, 48);
        }
    };

    drawRoute(waypointCoords);

    try {
        const roadCoords = await fetchRoadGeometry(waypointCoords);
        if (selectedMapTripId === tripId) drawRoute(roadCoords);
    } catch (err) {
        console.warn("GeometrÃ­a de carretera no disponible:", err.message);
    }
}

function updateMapData() {
    gmapMarkers.forEach((m) => m.setMap(null));
    gmapMarkers = [];
    gmapConnections.forEach((p) => p.setMap(null));
    gmapConnections = [];

    state.connections.forEach((connection) => {
        const origin = state.departments.find((d) => d.id === connection.origin_id);
        const destination = state.departments.find((d) => d.id === connection.destination_id);
        if (!origin || !destination || !origin.latitude || !destination.latitude) return;
        const poly = new google.maps.Polyline({
            path: [
                { lat: Number(origin.latitude), lng: Number(origin.longitude) },
                { lat: Number(destination.latitude), lng: Number(destination.longitude) }
            ],
            strokeColor: "#67e8f9",
            strokeOpacity: 0.45,
            strokeWeight: 2,
            map
        });
        gmapConnections.push(poly);
    });

    state.departments.filter((d) => d.latitude && d.longitude).forEach((dept) => {
        const marker = new google.maps.Marker({
            position: { lat: Number(dept.latitude), lng: Number(dept.longitude) },
            map,
            title: dept.name,
            icon: {
                path: google.maps.SymbolPath.CIRCLE,
                scale: 8,
                fillColor: "#fb923c",
                fillOpacity: 1,
                strokeColor: "#ffffff",
                strokeWeight: 2.2
            },
            label: {
                text: dept.code,
                color: "#ffffff",
                fontSize: "10px",
                fontWeight: "bold"
            }
        });
        marker.addListener("click", () => {
            if (activeInfoWindow) activeInfoWindow.close();
            activeInfoWindow = new google.maps.InfoWindow({
                content: `<div style="font-family:sans-serif;padding:2px"><strong>${escapeHtml(dept.name)}</strong><br><small>${escapeHtml(dept.code)}</small></div>`
            });
            activeInfoWindow.open(map, marker);
        });
        gmapMarkers.push(marker);
    });

    if (selectedMapTripId && state.trips.some((t) => t.id === selectedMapTripId)) {
        focusMapTripById(selectedMapTripId, { shouldFit: false });
        return;
    }

    selectedMapTripId = null;
    const selector = document.getElementById("map-trip-select");
    if (selector) selector.value = "";
    clearHighlightedRoute();
    updateMapRouteSummary(null);
    fitMapToDepartments();
}

function clearHighlightedRoute() {
    if (gmapRoutePolyline) {
        gmapRoutePolyline.setMap(null);
        gmapRoutePolyline = null;
    }
    gmapRouteMarkers.forEach((m) => m.setMap(null));
    gmapRouteMarkers = [];
}

function fitMapToDepartments() {
    if (mapHasAutoFit) return;
    const depts = state.departments.filter((d) => d.latitude && d.longitude);
    if (depts.length < 2) return;
    const bounds = new google.maps.LatLngBounds();
    depts.forEach((d) => bounds.extend({ lat: Number(d.latitude), lng: Number(d.longitude) }));
    map.fitBounds(bounds);
    mapHasAutoFit = true;
}

function updateMapRouteSummary(trip) {
    const summary = document.getElementById("map-route-summary");
    const hint = document.getElementById("map-summary-hint");
    if (!summary || !hint) return;
    if (!trip) {
        summary.classList.add("is-empty");
        hint.textContent = "Selecciona un viaje para ver la ruta Ã³ptima destacada.";
        setSummaryField("map-summary-code", "-");
        setSummaryField("map-summary-origin", "-");
        setSummaryField("map-summary-destination", "-");
        setSummaryField("map-summary-distance", "-");
        setSummaryField("map-summary-cost", "-");
        setSummaryField("map-summary-fuel", "-");
        setSummaryField("map-summary-status", "-");
        return;
    }
    summary.classList.remove("is-empty");
    hint.textContent = "Ruta resaltada con nodos de inicio, intermedios y fin.";
    setSummaryField("map-summary-code", escapeHtml(trip.code));
    setSummaryField("map-summary-origin", escapeHtml(trip.origin_name));
    setSummaryField("map-summary-destination", escapeHtml(trip.destination_name));
    setSummaryField("map-summary-distance", `${trip.total_distance_km.toFixed(2)} km`);
    setSummaryField("map-summary-cost", `Q ${trip.estimated_cost.toFixed(2)}`);
    setSummaryField("map-summary-fuel", `${trip.estimated_fuel_gallons.toFixed(2)} gal`);
    setSummaryField("map-summary-status", statusChip(trip.status));
}

function setSummaryField(id, value) {
    const node = document.getElementById(id);
    if (!node) return;
    if (typeof value === "string" && value.includes("<")) {
        node.innerHTML = value;
        return;
    }
    node.textContent = value;
}

// â”€â”€ FORM HANDLERS â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

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
        showToast("VehÃ­culo registrado.");
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
        showToast("Selecciona un vehÃ­culo.", true);
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
        showToast(`AcciÃ³n "${action}" ejecutada.`);
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

async function onDepartmentSubmit(event) {
    event.preventDefault();
    const form = event.currentTarget;
    const payload = {
        code: form.code.value.trim(),
        name: form.name.value.trim(),
        latitude: form.latitude.value !== "" ? Number(form.latitude.value) : null,
        longitude: form.longitude.value !== "" ? Number(form.longitude.value) : null,
    };
    try {
        await postJson(API.departments, payload);
        form.reset();
        showToast("Departamento registrado.");
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

// â”€â”€ DISPLAY â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

function showPlannerResult(trip) {
    const box = document.getElementById("planner-result");
    const fuelCostLine = trip.estimated_fuel_cost_gtq != null
        ? `<p><strong>Costo de combustible:</strong> Q ${trip.estimated_fuel_cost_gtq.toFixed(2)} <small>(Q ${trip.fuel_price_gtq_gal?.toFixed(2)}/gal al momento)</small></p>`
        : "";
    box.innerHTML = `
        <h3>Resultado de planificaciÃ³n</h3>
        <p><strong>CÃ³digo:</strong> ${escapeHtml(trip.code)}</p>
        <p><strong>VehÃ­culo:</strong> ${escapeHtml(trip.vehicle_plate)}</p>
        <p><strong>Conductor:</strong> ${escapeHtml(trip.driver_name || "No asignado")}</p>
        <p><strong>Ruta Ã³ptima:</strong> ${escapeHtml(trip.route_nodes.join(" â†’ "))}</p>
        <p><strong>Distancia:</strong> ${trip.total_distance_km.toFixed(2)} km</p>
        <p><strong>Combustible estimado:</strong> ${trip.estimated_fuel_gallons.toFixed(2)} galones</p>
        ${fuelCostLine}
        <p><strong>Costo operativo estimado:</strong> Q ${trip.estimated_cost.toFixed(2)}</p>
        <p><strong>Pedidos asociados:</strong> ${trip.orders.length}</p>
    `;
}

function buildTripActions(trip) {
    const role = state.currentUser ? state.currentUser.role : "operator";
    if (role === "operator") return "â€”";
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

// â”€â”€ CHART â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

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

// â”€â”€ HTTP â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

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

// â”€â”€ HELPERS â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

function statusLabel(status) {
    const labels = {
        pending: "Pendiente", assigned: "Asignado", in_transit: "En trÃ¡nsito",
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
