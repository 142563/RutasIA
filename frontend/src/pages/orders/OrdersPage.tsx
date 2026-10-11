import { AnimatePresence, motion } from "motion/react";
import { ChevronRightIcon, MapPinIcon, PackageIcon, PlusIcon, RouteIcon, SearchIcon, XIcon } from "lucide-react";
import * as React from "react";
import { useNavigate } from "react-router";
import { NotificationsSent } from "@/components/NotificationsSent";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/field";
import { EmptyState, ErrorNote, PageHeader, StatusDot } from "@/components/ui/misc";
import { AnimatedTabs, EASE, Skeleton } from "@/components/ui/motion";
import { Sheet } from "@/components/ui/sheet";
import { formatClock } from "@/lib/format";
import { PRIORITIES, STATUS, useOrders } from "@/lib/orders";
import type { Order, OrderStatus } from "@/lib/types";
import { cn } from "@/lib/utils";
import { NewOrderSheet } from "./NewOrderSheet";

type Tab = "all" | OrderStatus;

const TABS: { value: Tab; label: string }[] = [
  { value: "all", label: "Todos" },
  { value: "pending", label: "Pendientes" },
  { value: "assigned", label: "Asignados" },
  { value: "in_transit", label: "En ruta" },
  { value: "delivered", label: "Entregados" },
  { value: "failed", label: "No entregados" },
];

// Rejilla compartida por encabezado y filas: casilla, pedido, dirección, peso, estado, creado, detalle
const GRID = "grid grid-cols-[20px_minmax(0,1.1fr)_minmax(0,1.6fr)_76px_128px_92px_28px] items-center gap-x-4 px-6 lg:px-8";

function createdLabel(iso: string) {
  const created = new Date(iso);
  const sameDay = created.toDateString() === new Date().toDateString();
  return sameDay ? `Hoy ${formatClock(iso)}` : created.toLocaleDateString("es-GT", { day: "numeric", month: "short" });
}

function SkeletonRows() {
  return (
    <div aria-busy="true" aria-label="Cargando pedidos">
      {Array.from({ length: 8 }, (_, i) => (
        <div key={i} className={cn(GRID, "hidden h-14 border-b border-line sm:grid")}>
          <Skeleton className="size-4" />
          <div className="space-y-1.5"><Skeleton className="h-3.5 w-32" /><Skeleton className="h-3 w-20" /></div>
          <Skeleton className="h-3.5 w-3/4" />
          <Skeleton className="ml-auto h-3.5 w-12" />
          <Skeleton className="h-3.5 w-20" />
          <Skeleton className="ml-auto h-3.5 w-14" />
          <span />
        </div>
      ))}
      <div className="space-y-3 p-4 sm:hidden">
        {[0, 1, 2].map((i) => <Skeleton key={i} className="h-36 w-full rounded-xl" />)}
      </div>
    </div>
  );
}

/** Detalle que se despliega bajo la fila, sin salir de la lista. */
function Detail({ order }: { order: Order }) {
  const priority = PRIORITIES.find((p) => p.value === order.priority)?.label ?? order.priority;
  const items: [string, React.ReactNode][] = [
    ["Teléfono", order.phone ? <span className="num">{order.phone}</span> : "—"],
    ...(order.recipient_email ? ([["Correo", <span className="break-all">{order.recipient_email}</span>]] as [string, React.ReactNode][]) : []),
    ["Bultos", <span className="num">{order.package_count}</span>],
    ["Prioridad", priority],
    ["Referencias", order.reference || "—"],
    ["Punto en la red vial", order.node?.name ?? "—"],
    ["Coordenadas", <span className="num">{order.latitude.toFixed(4)}, {order.longitude.toFixed(4)}</span>],
  ];
  return (
    <div className="px-6 pb-4 pt-1 sm:pl-[60px] lg:pl-[68px] lg:pr-8">
      <dl className="grid gap-x-8 gap-y-3 sm:grid-cols-2 lg:grid-cols-3">
        {items.map(([k, v]) => (
          <div key={k} className="min-w-0">
            <dt className="text-xs text-ink-2">{k}</dt>
            <dd className="mt-0.5 break-words text-[13px] text-ink-3">{v}</dd>
          </div>
        ))}
      </dl>
      <div className="mt-4"><NotificationsSent filter={{ order: order.id }} /></div>
    </div>
  );
}

function OrderRow({ order, checked, open, fresh, onToggleCheck, onToggleOpen, onPlan }: {
  order: Order; checked: boolean; open: boolean; fresh: boolean;
  onToggleCheck: () => void; onToggleOpen: () => void; onPlan: () => void;
}) {
  const selectable = order.status === "pending";
  return (
    <motion.div
      layout="position"
      initial={{ opacity: 0, y: 4 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0 }}
      transition={{ duration: 0.2, ease: EASE }}
      className={cn("group border-b border-line transition-colors duration-700", fresh && "bg-accent-soft", checked && "bg-hover/70", !fresh && !checked && open && "bg-hover/40")}
    >
      <div className="p-4 sm:hidden">
        <div className="flex items-start gap-2">
          <label className="grid min-h-11 min-w-11 shrink-0 place-items-center">
            <input type="checkbox" className="size-4 accent-ink" aria-label={`Seleccionar ${order.code}`}
              checked={checked} disabled={!selectable} onChange={onToggleCheck} />
          </label>
          <button type="button" onClick={onToggleOpen} aria-expanded={open} className="min-h-11 min-w-0 flex-1 text-left">
            <span className="block break-words text-sm font-medium">{order.recipient}</span>
            <span className="num block text-xs text-ink-2">{order.code}</span>
          </button>
          <button type="button" onClick={onToggleOpen} aria-expanded={open} aria-label={open ? `Ocultar detalle de ${order.code}` : `Ver detalle de ${order.code}`}
            className="grid size-11 shrink-0 place-items-center rounded-md text-ink-2 hover:bg-hover">
            <ChevronRightIcon className={cn("size-4 transition-transform duration-200", open && "rotate-90")} />
          </button>
        </div>
        <div className="mt-2 flex flex-wrap items-center justify-between gap-2">
          <StatusDot color={STATUS[order.status].color}>{order.status_label}</StatusDot>
          <span className="num text-[13px]">{order.weight_kg.toLocaleString("es-GT")} kg · {order.package_count} bultos</span>
        </div>
        {order.priority === "high" ? <p className="mt-1 text-xs font-medium text-err">Prioridad alta</p> : null}
        <p className="mt-2 break-words text-[13px] text-ink-3">{order.address}</p>
        <p className="mt-1 break-words text-xs text-ink-2">{order.region?.name ?? ""} · {createdLabel(order.created_at)}</p>
        {selectable ? <Button variant="outline" className="mt-3 min-h-11 w-full" onClick={onPlan} aria-label={`Planificar ruta con ${order.code}`}><RouteIcon /> Planificar</Button> : null}
      </div>
      <div className={cn(GRID, "relative hidden min-h-14 py-2.5 transition-colors hover:bg-hover/50 sm:grid")}>
        <input type="checkbox" className="size-4 accent-ink" aria-label={`Seleccionar ${order.code}`}
          checked={checked} disabled={!selectable} onChange={onToggleCheck} />
        <button type="button" onClick={onToggleOpen} aria-expanded={open} className="min-w-0 text-left focus-visible:outline-offset-4">
          <span className="block truncate text-sm font-medium">
            {order.recipient}
            {order.priority === "high" ? <span className="ml-2 text-xs font-medium text-err">Prioridad alta</span> : null}
          </span>
          <span className="num block text-xs text-ink-2">{order.code}</span>
        </button>
        <span className="min-w-0">
          <span className="block truncate text-[13px] text-ink-3">{order.address}</span>
          <span className="block truncate text-xs text-ink-2">{order.region?.name ?? ""}</span>
        </span>
        <span className="num whitespace-nowrap text-right text-[13px]">{order.weight_kg.toLocaleString("es-GT")} kg</span>
        <StatusDot color={STATUS[order.status].color} className="whitespace-nowrap">{order.status_label}</StatusDot>
        <span className={cn("num whitespace-nowrap text-right text-xs text-ink-2 transition-opacity", selectable && "group-hover:opacity-0 group-focus-within:opacity-0")}>{createdLabel(order.created_at)}</span>
        {/* Acción al pasar el mouse o enfocar con el teclado; flota sobre la columna "Creado" */}
        {selectable ? (
          <span className="pointer-events-none absolute right-[72px] opacity-0 transition-opacity group-hover:pointer-events-auto group-hover:opacity-100 group-focus-within:pointer-events-auto group-focus-within:opacity-100 lg:right-[80px]">
            <Button variant="outline" size="sm" onClick={onPlan} aria-label={`Planificar ruta con ${order.code}`}><RouteIcon /> Planificar</Button>
          </span>
        ) : null}
        <button type="button" onClick={onToggleOpen} aria-label={open ? `Ocultar detalle de ${order.code}` : `Ver detalle de ${order.code}`}
          className="grid size-7 place-items-center rounded-md text-ink-2 transition-colors hover:bg-hover hover:text-ink">
          <ChevronRightIcon className={cn("size-4 transition-transform duration-200", open && "rotate-90")} />
        </button>
      </div>
      <AnimatePresence initial={false}>
        {open ? (
          <motion.div key="detail" initial={{ height: 0, opacity: 0 }} animate={{ height: "auto", opacity: 1 }} exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.22, ease: EASE }} className="overflow-hidden">
            <Detail order={order} />
          </motion.div>
        ) : null}
      </AnimatePresence>
    </motion.div>
  );
}

export function OrdersPage() {
  const navigate = useNavigate();
  const [tab, setTab] = React.useState<Tab>("pending");
  const [search, setSearch] = React.useState("");
  const [query, setQuery] = React.useState("");
  const [selected, setSelected] = React.useState<Set<number>>(new Set());
  const [expanded, setExpanded] = React.useState<number | null>(null);
  const [sheetOpen, setSheetOpen] = React.useState(false);
  const [byRegion, setByRegion] = React.useState(false);
  const [freshCode, setFreshCode] = React.useState<string | null>(null);

  React.useEffect(() => {
    const t = setTimeout(() => setQuery(search.trim()), 250);
    return () => clearTimeout(t);
  }, [search]);

  // El pedido recién creado se resalta unos segundos
  React.useEffect(() => {
    if (!freshCode) return;
    const t = setTimeout(() => setFreshCode(null), 3000);
    return () => clearTimeout(t);
  }, [freshCode]);

  const orders = useOrders({ status: tab, q: query });
  const rows = React.useMemo(() => orders.data?.orders ?? [], [orders.data]);
  const counts = orders.data?.counts ?? {};
  const selectable = (o: Order) => o.status === "pending";
  const selectedRows = rows.filter((o) => selected.has(o.id));
  const selectedWeight = selectedRows.reduce((sum, o) => sum + o.weight_kg, 0);
  const allSelectable = rows.filter(selectable);
  const allChecked = allSelectable.length > 0 && allSelectable.every((o) => selected.has(o.id));

  // Grupos por región (solo si se pide); si no, un único grupo sin título
  const groups = React.useMemo(() => {
    if (!byRegion) return [{ name: "", items: rows }];
    const map = new Map<string, Order[]>();
    for (const o of rows) {
      const key = o.region?.name ?? "Sin región";
      map.set(key, [...(map.get(key) ?? []), o]);
    }
    return [...map.entries()].sort((a, b) => b[1].length - a[1].length).map(([name, items]) => ({ name, items }));
  }, [rows, byRegion]);

  function toggle(id: number) {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }
  function changeTab(value: Tab) {
    setTab(value);
    setSelected(new Set());
    setExpanded(null);
  }

  return (
    <Sheet open={sheetOpen} onOpenChange={setSheetOpen}>
      <div className="flex min-h-full flex-col">
        <PageHeader
          title="Pedidos"
          subtitle={`${counts.pending ?? 0} pendientes de asignar`}
          actions={<Button className="max-sm:min-h-11" onClick={() => setSheetOpen(true)}><PlusIcon /> Nuevo pedido</Button>}
        />

        <div className="flex flex-wrap items-center justify-between gap-3 border-b border-line px-6 py-3 lg:px-8">
          <AnimatedTabs id="orders-status" label="Estado" value={tab} onChange={changeTab}
            className="max-w-full overflow-x-auto max-sm:[&_button]:min-h-11"
            options={TABS.map((t) => ({
              value: t.value,
              label: <>{t.label}<span className="num text-xs text-ink-2">{counts[t.value] ?? 0}</span></>,
            }))} />
          <div className="flex w-full items-center gap-2 sm:w-auto">
            <Button variant={byRegion ? "outline" : "ghost"} size="sm" className="max-sm:min-h-11" aria-pressed={byRegion} onClick={() => setByRegion((v) => !v)}>
              <MapPinIcon /> Por región
            </Button>
            <label className="relative w-full sm:w-60">
              <span className="sr-only">Buscar pedidos</span>
              <SearchIcon className="absolute left-2.5 top-1/2 size-4 -translate-y-1/2 text-ink-2" aria-hidden />
              <Input placeholder="Buscar pedidos" className="h-9 pl-8 text-[13px] max-sm:min-h-11" value={search} onChange={(e) => setSearch(e.target.value)} />
            </label>
          </div>
        </div>

        <div className="flex-1 overflow-x-auto">
          {/* El ancho mínimo solo con filas: así el estado vacío no queda con scroll horizontal */}
          <div className={rows.length > 0 ? "sm:min-w-[760px]" : undefined}>
            {rows.length > 0 ? (
              <div className={cn(GRID, "hidden h-9 border-b border-line text-xs text-ink-2 sm:grid")}>
                <input type="checkbox" aria-label="Seleccionar todos los pendientes" className="size-4 accent-ink"
                  checked={allChecked} disabled={allSelectable.length === 0}
                  onChange={() => setSelected(allChecked ? new Set() : new Set(allSelectable.map((o) => o.id)))} />
                <span>Destinatario</span><span>Dirección</span><span className="text-right">Peso</span><span>Estado</span><span className="text-right">Creado</span><span />
              </div>
            ) : null}
            {rows.length > 0 ? (
              <label className="flex min-h-11 items-center gap-3 border-b border-line px-6 text-sm sm:hidden">
                <input type="checkbox" aria-label="Seleccionar todos los pendientes" className="size-4 accent-ink"
                  checked={allChecked} disabled={allSelectable.length === 0}
                  onChange={() => setSelected(allChecked ? new Set() : new Set(allSelectable.map((o) => o.id)))} />
                Seleccionar pendientes
              </label>
            ) : null}
            {orders.isPending ? <SkeletonRows /> : null}
            {orders.error ? <div className="p-6"><ErrorNote error={orders.error} /></div> : null}
            {orders.data && rows.length === 0 ? (
              <EmptyState icon={<PackageIcon />} title={query ? "Sin resultados" : "No hay pedidos en este estado"}
                action={!query ? <Button variant="outline" onClick={() => setSheetOpen(true)}><PlusIcon /> Nuevo pedido</Button> : null}>
                {query ? `Nada coincide con “${query}”.` : "Los pedidos nuevos aparecen como pendientes."}
              </EmptyState>
            ) : null}
            {groups.map((g) => (
              <section key={g.name || "todos"} aria-label={g.name || undefined}>
                {g.name ? (
                  <div className="flex items-center gap-2 border-b border-line bg-bg px-6 py-1.5 text-xs font-medium text-ink-3 lg:px-8">
                    {g.name}<span className="num font-normal text-ink-2">{g.items.length}</span>
                  </div>
                ) : null}
                <AnimatePresence initial={false}>
                  {g.items.map((o) => (
                    <OrderRow key={o.id} order={o} checked={selected.has(o.id)} open={expanded === o.id} fresh={o.code === freshCode}
                      onToggleCheck={() => toggle(o.id)}
                      onToggleOpen={() => setExpanded((cur) => (cur === o.id ? null : o.id))}
                      onPlan={() => navigate(`/planificar?pedidos=${o.id}`)} />
                  ))}
                </AnimatePresence>
              </section>
            ))}
          </div>
        </div>

        <AnimatePresence>
          {selected.size > 0 ? (
            <motion.div key="bar" initial={{ y: 24, opacity: 0 }} animate={{ y: 0, opacity: 1 }} exit={{ y: 24, opacity: 0 }}
              transition={{ duration: 0.22, ease: EASE }}
              className="sticky bottom-0 flex flex-wrap items-center justify-between gap-3 border-t border-line bg-elevated px-6 py-3 shadow-lift lg:px-8">
              <p className="text-sm">
                <span className="num font-medium">{selected.size}</span> seleccionados
                <span className="num text-ink-2"> · {selectedWeight.toLocaleString("es-GT", { maximumFractionDigits: 1 })} kg</span>
              </p>
              <div className="flex gap-2 max-sm:[&_button]:min-h-11">
                <Button variant="ghost" onClick={() => setSelected(new Set())}><XIcon /> Quitar</Button>
                <Button onClick={() => navigate(`/planificar?pedidos=${[...selected].join(",")}`)}><RouteIcon /> Planificar ruta</Button>
              </div>
            </motion.div>
          ) : null}
        </AnimatePresence>
      </div>
      <NewOrderSheet onDone={(code) => {
        setSheetOpen(false);
        if (code) { setTab("pending"); setSearch(""); setFreshCode(code); }
      }} />
    </Sheet>
  );
}
