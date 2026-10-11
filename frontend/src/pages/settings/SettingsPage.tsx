import { BuildingIcon, PencilIcon, PlusIcon, TruckIcon, UserCogIcon, UsersIcon } from "lucide-react";
import { motion } from "motion/react";
import * as React from "react";
import { Navigate, Route, Routes, useNavigate, useLocation } from "react-router";
import { Button } from "@/components/ui/button";
import { EmptyState, ErrorNote, PageHeader, StatusDot } from "@/components/ui/misc";
import { SPRING, Skeleton, Stagger, StaggerItem } from "@/components/ui/motion";
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
      { header: "Correo", cell: (u) => (u.email ? <span title={u.email}>{u.email}</span> : dim("Sin correo")) },
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
  // Columnas de datos iguales entre sí, luego estado y acciones
  const cols = { gridTemplateColumns: `repeat(${config.columns.length}, minmax(0, 1fr)) 96px 72px` };

  return (
    <Sheet open={editing !== null} onOpenChange={(open) => !open && close()}>
      <div className="min-w-0 flex-1">
        <div className="flex items-center justify-between gap-3 pb-3">
          <h2 className="text-base font-semibold">
            {config.label}
            {list.data ? <span className="num ml-2 text-[13px] font-normal text-ink-2">{items.filter((i) => i.is_active).length} activos de {items.length}</span> : null}
          </h2>
          {items.length > 0 ? add : null}
        </div>
        <div className="overflow-x-auto rounded-xl border border-line bg-surface shadow-card">
          <div className="min-w-[620px]">
            {list.isPending ? (
              <div aria-busy="true" aria-label="Cargando">
                {Array.from({ length: 4 }, (_, i) => (
                  <div key={i} className="flex h-14 items-center gap-6 border-b border-line px-5 last:border-0">
                    <Skeleton className="h-3.5 w-40" /><Skeleton className="h-3.5 w-28" /><Skeleton className="ml-auto h-3.5 w-16" />
                  </div>
                ))}
              </div>
            ) : null}
            {list.error ? <div className="p-5"><ErrorNote error={list.error} /></div> : null}
            {list.data && items.length === 0 ? (
              <EmptyState icon={config.icon} title={config.empty} action={add} />
            ) : null}
            {items.length > 0 ? (
              <>
                <div className="grid items-center gap-x-4 border-b border-line px-5 py-2.5 text-xs text-ink-2" style={cols}>
                  {config.columns.map((c) => <span key={c.header} className={c.className}>{c.header}</span>)}
                  <span>Estado</span><span className="sr-only">Acciones</span>
                </div>
                <Stagger key={config.kind}>
                  {items.map((item) => (
                    <StaggerItem key={item.id}
                      className={cn("group grid min-h-14 items-center gap-x-4 border-b border-line px-5 py-2.5 text-sm transition-colors last:border-0 hover:bg-hover/50", !item.is_active && "text-ink-2")}
                      style={cols}>
                      {config.columns.map((c) => <span key={c.header} className={cn("min-w-0 truncate", c.className)}>{c.cell(item)}</span>)}
                      <StatusDot color={item.is_active ? COLORS.on : COLORS.off}>{item.is_active ? "Activo" : "Inactivo"}</StatusDot>
                      <span className="text-right opacity-0 transition-opacity focus-within:opacity-100 group-hover:opacity-100 max-md:opacity-100">
                        <Button variant="ghost" size="sm" onClick={() => setEditing(item)} aria-label={`Editar ${config.singular}`}><PencilIcon /> Editar</Button>
                      </span>
                    </StaggerItem>
                  ))}
                </Stagger>
              </>
            ) : null}
          </div>
        </div>
      </div>
      {editing !== null ? <SheetFor kind={config.kind} item={current} onDone={close} /> : null}
    </Sheet>
  );
}

/** Ítem de la subnavegación lateral: indicador que se desliza y conteo de activos. */
function NavItem({ config, active, onClick }: { config: (typeof ORDER)[number]; active: boolean; onClick: () => void }) {
  const list = useFleet(config.kind);
  const count = (list.data as Item[] | undefined)?.filter((i) => i.is_active).length;
  return (
    <button type="button" role="tab" aria-selected={active} onClick={onClick}
      className={cn("relative flex h-10 shrink-0 items-center gap-2.5 rounded-lg px-3 text-[13px] transition-colors [&_svg]:size-4", active ? "font-medium text-ink" : "text-ink-2 hover:text-ink")}>
      {active ? <motion.span layoutId="settings-nav" transition={SPRING} className="absolute inset-0 rounded-lg bg-surface shadow-card ring-1 ring-line" aria-hidden /> : null}
      <span className="relative z-10 flex items-center gap-2.5">{config.icon}{config.label}</span>
      {count !== undefined ? <span className="num relative z-10 ml-auto text-xs text-ink-2">{count}</span> : null}
    </button>
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
      <div className="flex flex-col gap-4 px-6 pb-8 pt-4 lg:flex-row lg:gap-8 lg:px-8">
        <div role="tablist" aria-label="Sección" aria-orientation="vertical"
          className="flex gap-1 overflow-x-auto lg:sticky lg:top-4 lg:w-52 lg:shrink-0 lg:flex-col lg:self-start lg:overflow-visible">
          {ORDER.map((t) => (
            <NavItem key={t.path} config={t} active={pathname.includes(`/configuracion/${t.path}`)} onClick={() => navigate(`/configuracion/${t.path}`)} />
          ))}
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
    </div>
  );
}
