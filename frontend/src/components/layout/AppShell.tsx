import {
  FlaskConicalIcon, HouseIcon, LogOutIcon, MenuIcon, PackageIcon, RouteIcon, TruckIcon, XIcon,
} from "lucide-react";
import * as React from "react";
import { NavLink, Outlet, useLocation, useNavigate } from "react-router";
import { useLogout, useUser } from "@/lib/auth";
import { isRealData, useNetwork } from "@/lib/queries";
import { cn } from "@/lib/utils";

interface NavItem {
  to: string;
  label: string;
  icon: React.ComponentType<{ className?: string }>;
  adminOnly?: boolean;
}

// Cuatro pasos del día a día y un solo lugar para lo de la tesis
const MAIN: NavItem[] = [
  { to: "/", label: "Hoy", icon: HouseIcon },
  { to: "/pedidos", label: "Pedidos", icon: PackageIcon },
  { to: "/planificar", label: "Planificar", icon: RouteIcon },
  { to: "/rutas", label: "Rutas", icon: TruckIcon },
];
const ANALYSIS: NavItem[] = [
  { to: "/analisis", label: "Análisis", icon: FlaskConicalIcon },
];

export function Logo() {
  return (
    <div className="flex items-center gap-2">
      <svg width="22" height="22" viewBox="0 0 32 32" aria-hidden>
        <rect width="32" height="32" rx="8" fill="#111113" />
        <path d="M9 22c0-5 4-5 7-8s3-5 7-5" fill="none" stroke="#fff" strokeWidth="2.6" strokeLinecap="round" />
        <circle cx="9" cy="22" r="2.6" fill="#fff" />
        <circle cx="23" cy="9" r="2.6" fill="#fff" />
      </svg>
      {/* Nombre provisional (docs/PLAN.md §12): aún no se decide */}
      <span className="text-[17px] font-semibold tracking-tight">enruta</span>
    </div>
  );
}

function NavItemLink({ item, onNavigate }: { item: NavItem; onNavigate: () => void }) {
  const Icon = item.icon;
  return (
    <NavLink
      to={item.to}
      end={item.to === "/"}
      onClick={onNavigate}
      className={({ isActive }) =>
        cn(
          "flex h-9 items-center gap-2.5 rounded-lg px-2.5 text-sm text-ink-3 transition-colors hover:bg-hover hover:text-ink",
          isActive && "bg-hover font-medium text-ink",
        )
      }
    >
      <Icon className="size-[17px]" />
      {item.label}
    </NavLink>
  );
}

export function AppShell() {
  const user = useUser();
  const logout = useLogout();
  const navigate = useNavigate();
  const location = useLocation();
  const [open, setOpen] = React.useState(false);
  React.useEffect(() => setOpen(false), [location.pathname]);

  const initials = user.full_name.split(" ").map((w) => w[0]).slice(0, 2).join("").toUpperCase();
  const visible = (items: NavItem[]) => items.filter((i) => !i.adminOnly || user.role === "admin");
  const network = useNetwork();
  const sampleData = network.data ? !isRealData(network.data.data_source) : false;

  const sidebar = (
    <nav aria-label="Principal" className="flex h-full flex-col gap-0.5 px-3 pb-4 pt-6">
      <div className="px-2.5 pb-6"><Logo /></div>
      {visible(MAIN).map((item) => <NavItemLink key={item.to} item={item} onNavigate={() => setOpen(false)} />)}
      <span className="mt-5" />
      {visible(ANALYSIS).map((item) => <NavItemLink key={item.to} item={item} onNavigate={() => setOpen(false)} />)}
      <div className="flex-1" />
      {sampleData ? (
        <p className="mx-1 mb-3 flex items-start gap-2 rounded-lg bg-hover px-2.5 py-2 text-xs text-ink-3"
          title="Tramos estimados y tráfico sintético: sirven para probar, no son resultados de la tesis.">
          <span className="mt-1 size-1.5 shrink-0 rounded-full bg-warn" aria-hidden />
          Datos de ejemplo. Para datos reales: preparar --google
        </p>
      ) : null}
      <div className="flex items-center gap-2.5 border-t border-line px-1 pt-4">
        <span className="grid size-8 shrink-0 place-items-center rounded-full bg-hover text-xs font-semibold">{initials}</span>
        <div className="min-w-0 flex-1">
          <p className="truncate text-[13px] font-medium">{user.full_name}</p>
          <p className="text-xs text-ink-2">{user.role_label}</p>
        </div>
        <button
          type="button"
          className="rounded-md p-1.5 text-ink-2 hover:bg-hover hover:text-ink"
          aria-label="Cerrar sesión"
          title="Cerrar sesión"
          onClick={() => logout.mutate(undefined, { onSettled: () => navigate("/login", { replace: true }) })}
        >
          <LogOutIcon className="size-4" />
        </button>
      </div>
    </nav>
  );

  return (
    <div className="flex h-full">
      <aside className="hidden w-[220px] shrink-0 border-r border-line lg:block">{sidebar}</aside>

      {/* Móvil: menú desplegable */}
      <div className="fixed inset-x-0 top-0 z-30 flex h-14 items-center justify-between border-b border-line bg-bg px-4 lg:hidden">
        <Logo />
        <button type="button" className="rounded-md p-2 hover:bg-hover" aria-label="Abrir menú" onClick={() => setOpen(true)}>
          <MenuIcon className="size-5" />
        </button>
      </div>
      {open ? (
        <div className="fixed inset-0 z-40 lg:hidden">
          <div className="absolute inset-0 bg-ink/20" onClick={() => setOpen(false)} />
          <aside className="absolute inset-y-0 left-0 w-[260px] border-r border-line bg-bg">
            <button type="button" className="absolute right-3 top-5 rounded-md p-1.5 hover:bg-hover" aria-label="Cerrar menú" onClick={() => setOpen(false)}>
              <XIcon className="size-4" />
            </button>
            {sidebar}
          </aside>
        </div>
      ) : null}

      <main className="min-w-0 flex-1 overflow-y-auto pt-14 lg:pt-0">
        <Outlet />
      </main>
    </div>
  );
}
