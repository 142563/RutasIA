import { BuildingIcon, PlusIcon, TruckIcon, UserCogIcon, UsersIcon } from "lucide-react";
import * as React from "react";
import { Navigate, Route, Routes, useNavigate, useLocation } from "react-router";
import { Button } from "@/components/ui/button";
import { EmptyState, ErrorNote, PageHeader, Spinner, StatusDot } from "@/components/ui/misc";
import { Sheet } from "@/components/ui/sheet";
import { useUser } from "@/lib/auth";
import { useFleet, type FleetKind, type FleetTypes } from "@/lib/fleet";
import { cn } from "@/lib/utils";
import { DepotSheet, DriverSheet, UserSheet, VehicleSheet } from "./FleetSheets";

interface Column<T> { header: string; className?: string; cell: (item: T) => React.ReactNode }

interface TabConfig<K extends FleetKind> {
  kind: K;
  path: string;
  label: string;
  singular: string;
  icon: React.ReactNode;
  empty: string;
  columns: Column<FleetTypes[K]>[];
}

const kg = (n: number) => `${n.toLocaleString("es-GT")} kg`;
const dim = (text: string) => <span className="text-ink-2">{text}</span>;

const TABS = {
  depots: {
    kind: "depots", path: "bodegas", label: "Bodegas", singular: "bodega", icon: <BuildingIcon />,
    empty: "Aún no hay bodegas. Agrega la primera para poder planificar rutas.",
    columns: [
      { header: "Bodega", cell: (d) => <span className="font-medium">{d.name}</span> },
      { header: "Dirección", cell: (d) => (d.address ? d.address : dim("—")) },
      { header: "Punto de la red vial", cell: (d) => (d.node ? d.node.name : dim("Se asigna al cargar la red vial")) },
    ],
  } satisfies TabConfig<"depots">,
  drivers: {
    kind: "drivers", path: "pilotos", label: "Pilotos", singular: "piloto", icon: <UsersIcon />,
    empty: "Aún no hay pilotos. Agrega el primero para poder asignarle rutas.",
    columns: [
      { header: "Piloto", cell: (d) => <span className="font-medium">{d.name}</span> },
      { header: "Teléfono", cell: (d) => (d.phone ? <span className="num">{d.phone}</span> : dim("—")) },
      { header: "Licencia", cell: (d) => <span className="num">{d.license_number}</span> },
      { header: "Cuenta del celular", cell: (d) => (d.user ? d.user.username : dim("Sin cuenta")) },
    ],
  } satisfies TabConfig<"drivers">,
  vehicles: {
    kind: "vehicles", path: "camiones", label: "Camiones", singular: "camión", icon: <TruckIcon />,
    empty: "Aún no hay camiones. Agrega el primero para poder planificar con su capacidad.",
    columns: [
      { header: "Placa", cell: (v) => <span className="num font-medium">{v.plate}</span> },
      { header: "Modelo", cell: (v) => v.model },
      { header: "Capacidad", className: "text-right", cell: (v) => <span className="num">{kg(v.capacity_kg)}</span> },
      { header: "Piloto fijo", cell: (v) => (v.driver ? v.driver.name : dim("Sin piloto fijo")) },
    ],
  } satisfies TabConfig<"vehicles">,
  users: {
    kind: "users", path: "usuarios", label: "Usuarios", singular: "usuario", icon: <UserCogIcon />,
    empty: "Aún no hay usuarios.",
    columns: [
      { header: "Usuario", cell: (u) => <span className="font-medium">{u.username}</span> },
      { header: "Nombre", cell: (u) => (u.full_name ? u.full_name : dim("—")) },
      { header: "Rol", cell: (u) => u.role_label },
    ],
  } satisfies TabConfig<"users">,
};

const ORDER = [TABS.depots, TABS.drivers, TABS.vehicles, TABS.users];
const COLORS = { on: "#1a7f4b", off: "#a3a6ac" };

type Item = { id: number; is_active: boolean };

function FleetTab<K extends FleetKind>({ config }: { config: TabConfig<K> }) {
  const list = useFleet(config.kind);
  const [editing, setEditing] = React.useState<FleetTypes[K] | "new" | null>(null);
  const items = (list.data ?? []) as (FleetTypes[K] & Item)[];
  const close = () => setEditing(null);
  const add = <Button onClick={() => setEditing("new")}><PlusIcon /> Agregar {config.singular}</Button>;
  const current = editing === "new" ? null : editing;

  return (
    <Sheet open={editing !== null} onOpenChange={(open) => !open && close()}>
      <div className="flex items-center justify-between gap-3 px-6 py-4 lg:px-8">
        <p className="text-[13px] text-ink-2">
          {list.data ? `${items.filter((i) => i.is_active).length} activos de ${items.length}` : ""}
        </p>
        {items.length > 0 ? add : null}
      </div>
      <div className="overflow-x-auto border-t border-line">
        {list.isPending ? <div className="p-8"><Spinner /></div> : null}
        {list.error ? <div className="p-6"><ErrorNote error={list.error} /></div> : null}
        {list.data && items.length === 0 ? (
          <EmptyState icon={config.icon} title={config.empty} action={add} />
        ) : null}
        {items.length > 0 ? (
          <table className="w-full min-w-[640px] text-sm">
            <thead>
              <tr className="border-b border-line text-left text-xs text-ink-2">
                {config.columns.map((c, i) => (
                  <th key={c.header} className={cn("py-2.5 pr-4 font-normal", i === 0 && "pl-6 lg:pl-8", c.className)}>{c.header}</th>
                ))}
                <th className="py-2.5 pr-4 font-normal">Estado</th>
                <th className="w-24 py-2.5 pr-6 lg:pr-8"><span className="sr-only">Acciones</span></th>
              </tr>
            </thead>
            <tbody>
              {items.map((item) => (
                <tr key={item.id} className={cn("border-b border-line transition-colors hover:bg-hover/50", !item.is_active && "text-ink-2")}>
                  {config.columns.map((c, i) => (
                    <td key={c.header} className={cn("py-3 pr-4", i === 0 && "pl-6 lg:pl-8", c.className)}>{c.cell(item)}</td>
                  ))}
                  <td className="whitespace-nowrap py-3 pr-4">
                    <StatusDot color={item.is_active ? COLORS.on : COLORS.off}>{item.is_active ? "Activo" : "Inactivo"}</StatusDot>
                  </td>
                  <td className="py-3 pr-6 text-right lg:pr-8">
                    <Button variant="ghost" size="sm" onClick={() => setEditing(item)}>Editar</Button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : null}
      </div>
      {editing !== null ? <SheetFor kind={config.kind} item={current} onDone={close} /> : null}
    </Sheet>
  );
}

function SheetFor({ kind, item, onDone }: { kind: FleetKind; item: unknown; onDone: () => void }) {
  switch (kind) {
    case "depots": return <DepotSheet item={item as FleetTypes["depots"] | null} onDone={onDone} />;
    case "drivers": return <DriverSheet item={item as FleetTypes["drivers"] | null} onDone={onDone} />;
    case "vehicles": return <VehicleSheet item={item as FleetTypes["vehicles"] | null} onDone={onDone} />;
    case "users": return <UserSheet item={item as FleetTypes["users"] | null} onDone={onDone} />;
  }
}

/** Configuración (solo administrador): bodegas, pilotos, camiones y usuarios. */
export function SettingsPage() {
  const user = useUser();
  const navigate = useNavigate();
  const { pathname } = useLocation();

  if (user.role !== "admin") {
    return (
      <div className="flex min-h-full flex-col">
        <PageHeader title="Configuración" />
        <EmptyState title="Solo el administrador puede cambiar la configuración">
          Pide a un administrador que agregue o edite bodegas, pilotos, camiones y usuarios.
        </EmptyState>
      </div>
    );
  }

  return (
    <div className="flex min-h-full flex-col">
      <PageHeader title="Configuración" subtitle="Los datos de tu empresa: dónde salen los camiones, quién los maneja y quién usa el sistema." />
      <div role="tablist" aria-label="Sección" className="flex gap-1 overflow-x-auto px-6 lg:px-8">
        {ORDER.map((t) => {
          const active = pathname.includes(`/configuracion/${t.path}`);
          return (
            <button key={t.path} role="tab" aria-selected={active} onClick={() => navigate(`/configuracion/${t.path}`)}
              className={cn(
                "-mb-px flex h-11 items-center whitespace-nowrap border-b-2 px-2.5 text-[13px] text-ink-2 transition-colors hover:text-ink",
                active ? "border-ink font-medium text-ink" : "border-transparent",
              )}>
              {t.label}
            </button>
          );
        })}
      </div>
      <Routes>
        <Route index element={<Navigate to="bodegas" replace />} />
        <Route path="bodegas" element={<FleetTab config={TABS.depots} />} />
        <Route path="pilotos" element={<FleetTab config={TABS.drivers} />} />
        <Route path="camiones" element={<FleetTab config={TABS.vehicles} />} />
        <Route path="usuarios" element={<FleetTab config={TABS.users} />} />
        <Route path="*" element={<Navigate to="bodegas" replace />} />
      </Routes>
    </div>
  );
}
