import { PackageIcon, PlusIcon, SearchIcon } from "lucide-react";
import * as React from "react";
import { useNavigate } from "react-router";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/field";
import { EmptyState, ErrorNote, PageHeader, Spinner, StatusDot } from "@/components/ui/misc";
import { Sheet } from "@/components/ui/sheet";
import { formatClock } from "@/lib/format";
import { STATUS, useOrders } from "@/lib/orders";
import type { Order, OrderStatus } from "@/lib/types";
import { cn } from "@/lib/utils";
import { NewOrderSheet } from "./NewOrderSheet";

const TABS: { value: "all" | OrderStatus; label: string }[] = [
  { value: "all", label: "Todos" },
  { value: "pending", label: "Pendientes" },
  { value: "assigned", label: "Asignados" },
  { value: "in_transit", label: "En ruta" },
  { value: "delivered", label: "Entregados" },
  { value: "failed", label: "No entregados" },
];

function createdLabel(iso: string) {
  const created = new Date(iso);
  const today = new Date();
  const sameDay = created.toDateString() === today.toDateString();
  return sameDay ? `Hoy ${formatClock(iso)}` : created.toLocaleDateString("es-GT", { day: "numeric", month: "short" });
}

export function OrdersPage() {
  const navigate = useNavigate();
  const [tab, setTab] = React.useState<"all" | OrderStatus>("pending");
  const [search, setSearch] = React.useState("");
  const [query, setQuery] = React.useState("");
  const [selected, setSelected] = React.useState<Set<number>>(new Set());
  const [sheetOpen, setSheetOpen] = React.useState(false);

  React.useEffect(() => {
    const t = setTimeout(() => setQuery(search.trim()), 250);
    return () => clearTimeout(t);
  }, [search]);

  const orders = useOrders({ status: tab, q: query });
  const rows = orders.data?.orders ?? [];
  const counts = orders.data?.counts ?? {};
  const selectable = (o: Order) => o.status === "pending";
  const selectedRows = rows.filter((o) => selected.has(o.id));
  const selectedWeight = selectedRows.reduce((sum, o) => sum + o.weight_kg, 0);
  const allSelectable = rows.filter(selectable);
  const allChecked = allSelectable.length > 0 && allSelectable.every((o) => selected.has(o.id));

  function toggle(id: number) {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  return (
    <Sheet open={sheetOpen} onOpenChange={setSheetOpen}>
      <div className="flex min-h-full flex-col">
        <PageHeader
          title="Pedidos"
          subtitle={`${counts.pending ?? 0} pendientes de asignar`}
          actions={<Button onClick={() => setSheetOpen(true)}><PlusIcon /> Nuevo pedido</Button>}
        />

        <div className="flex flex-wrap items-center justify-between gap-3 border-b border-line px-6 lg:px-8">
          <div role="tablist" aria-label="Estado" className="-mb-px flex gap-1 overflow-x-auto">
            {TABS.map((t) => (
              <button
                key={t.value}
                role="tab"
                aria-selected={tab === t.value}
                onClick={() => { setTab(t.value); setSelected(new Set()); }}
                className={cn(
                  "flex h-11 items-center gap-1.5 whitespace-nowrap border-b-2 px-2.5 text-[13px] text-ink-2 transition-colors hover:text-ink",
                  tab === t.value ? "border-ink font-medium text-ink" : "border-transparent",
                )}
              >
                {t.label}
                <span className="num text-xs text-ink-2">{counts[t.value] ?? 0}</span>
              </button>
            ))}
          </div>
          <label className="relative my-2 w-full sm:w-64">
            <span className="sr-only">Buscar pedidos</span>
            <SearchIcon className="absolute left-2.5 top-1/2 size-4 -translate-y-1/2 text-ink-2" aria-hidden />
            <Input placeholder="Buscar pedidos" className="pl-8" value={search} onChange={(e) => setSearch(e.target.value)} />
          </label>
        </div>

        <div className="flex-1 overflow-x-auto">
          {orders.isPending ? <div className="p-8"><Spinner /></div> : null}
          {orders.error ? <div className="p-6"><ErrorNote error={orders.error} /></div> : null}
          {orders.data && rows.length === 0 ? (
            <EmptyState icon={<PackageIcon />} title={query ? "Sin resultados" : "No hay pedidos en este estado"}
              action={!query ? <Button variant="outline" onClick={() => setSheetOpen(true)}><PlusIcon /> Nuevo pedido</Button> : null}>
              {query ? `Nada coincide con “${query}”.` : "Los pedidos nuevos aparecen como pendientes."}
            </EmptyState>
          ) : null}
          {rows.length > 0 ? (
            <table className="w-full min-w-[820px] text-sm">
              <thead>
                <tr className="border-b border-line text-left text-xs text-ink-2">
                  <th className="w-12 py-2.5 pl-6 pr-3 lg:pl-8">
                    <input type="checkbox" aria-label="Seleccionar todos los pendientes" className="size-4 accent-ink"
                      checked={allChecked} disabled={allSelectable.length === 0}
                      onChange={() => setSelected(allChecked ? new Set() : new Set(allSelectable.map((o) => o.id)))} />
                  </th>
                  <th className="py-2.5 font-normal">Código</th>
                  <th className="py-2.5 font-normal">Destinatario</th>
                  <th className="py-2.5 font-normal">Dirección</th>
                  <th className="py-2.5 text-right font-normal">Peso</th>
                  <th className="py-2.5 pl-6 font-normal">Estado</th>
                  <th className="py-2.5 pr-6 text-right font-normal lg:pr-8">Creado</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((o) => (
                  <tr key={o.id} className={cn("border-b border-line transition-colors hover:bg-hover/50", selected.has(o.id) && "bg-hover/60")}>
                    <td className="py-3 pl-6 pr-3 lg:pl-8">
                      <input type="checkbox" className="size-4 accent-ink" aria-label={`Seleccionar ${o.code}`}
                        checked={selected.has(o.id)} disabled={!selectable(o)} onChange={() => toggle(o.id)} />
                    </td>
                    <td className="num whitespace-nowrap py-3 pr-4 text-[13px] text-ink-3">{o.code}</td>
                    <td className="py-3">
                      <span className="font-medium">{o.recipient}</span>
                      {o.priority === "high" ? <span className="ml-2 text-xs font-medium text-err">Alta</span> : null}
                      {o.is_demo ? <span className="ml-2 text-xs text-ink-2">demo</span> : null}
                    </td>
                    <td className="max-w-[320px] py-3">
                      <span className="block truncate text-ink-3">{o.address}</span>
                      <span className="text-xs text-ink-2">Nodo: {o.node?.name ?? "—"}</span>
                    </td>
                    <td className="num whitespace-nowrap py-3 text-right">{o.weight_kg.toLocaleString("es-GT")} kg</td>
                    <td className="whitespace-nowrap py-3 pl-6"><StatusDot color={STATUS[o.status].color}>{o.status_label}</StatusDot></td>
                    <td className="num whitespace-nowrap py-3 pl-4 pr-6 text-right text-[13px] text-ink-2 lg:pr-8">{createdLabel(o.created_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : null}
        </div>

        {selected.size > 0 ? (
          <div className="sticky bottom-0 flex flex-wrap items-center justify-between gap-3 border-t border-line bg-surface px-6 py-3 lg:px-8">
            <p className="text-sm">
              <span className="num font-medium">{selected.size}</span> seleccionados
              <span className="num text-ink-2"> · {selectedWeight.toLocaleString("es-GT", { maximumFractionDigits: 1 })} kg</span>
            </p>
            <div className="flex gap-2">
              <Button variant="ghost" onClick={() => setSelected(new Set())}>Quitar</Button>
              <Button onClick={() => navigate(`/planificar?pedidos=${[...selected].join(",")}`)}>Planificar ruta</Button>
            </div>
          </div>
        ) : null}
      </div>
      <NewOrderSheet onDone={() => setSheetOpen(false)} />
    </Sheet>
  );
}
