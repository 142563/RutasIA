import {
  BellIcon, FlaskConicalIcon, HouseIcon, LogOutIcon, MonitorIcon, MoonIcon, PackageIcon, RouteIcon, SearchIcon,
  SettingsIcon, SunIcon, TruckIcon,
} from "lucide-react";
import { AnimatePresence, motion } from "motion/react";
import { DropdownMenu } from "radix-ui";
import * as React from "react";
import { Link, NavLink, Outlet, useLocation, useNavigate } from "react-router";
import { CommandPalette, type Command } from "@/components/layout/CommandPalette";
import { PageTransition, SPRING } from "@/components/ui/motion";
import { useLogout, useUser } from "@/lib/auth";
import { useDashboard } from "@/lib/dispatch";
import { useIncidents } from "@/lib/incidents";
import { isRealData, useNetwork } from "@/lib/queries";
import { useTheme, type ThemeChoice } from "@/lib/theme";
import { cn } from "@/lib/utils";

interface NavItem {
  to: string;
  label: string;
  icon: React.ComponentType<{ className?: string }>;
  adminOnly?: boolean;
}

// Cuatro pasos del día a día y un solo lugar para lo de la tesis
export const MAIN: NavItem[] = [
  { to: "/", label: "Hoy", icon: HouseIcon },
  { to: "/pedidos", label: "Pedidos", icon: PackageIcon },
  { to: "/planificar", label: "Planificar", icon: RouteIcon },
  { to: "/rutas", label: "Rutas", icon: TruckIcon },
];
export const ANALYSIS: NavItem[] = [
  { to: "/analisis", label: "Análisis", icon: FlaskConicalIcon },
  // Bodegas, pilotos, camiones y usuarios: solo el administrador
  { to: "/configuracion", label: "Configuración", icon: SettingsIcon, adminOnly: true },
];

/** Marca: una ruta de origen a destino; el destino en naranja de entrega. */
export function LogoMark({ size = 28 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 32 32" aria-hidden className="shrink-0">
      <rect width="32" height="32" rx="9" fill="var(--color-ink)" />
      <path d="M9 22c0-5 4-5 7-8s3-5 7-5" fill="none" stroke="var(--color-on-ink)" strokeWidth="2.6" strokeLinecap="round" />
      <circle cx="9" cy="22" r="2.6" fill="var(--color-on-ink)" />
      <circle cx="23" cy="9" r="3" fill="var(--color-delivery)" />
    </svg>
  );
}

export function Logo() {
  return (
    <div className="flex items-center gap-2">
      <LogoMark size={24} />
      {/* Nombre provisional (docs/PLAN.md §12): aún no se decide */}
      <span className="text-[17px] font-semibold tracking-tight">enruta</span>
    </div>
  );
}

function isActive(pathname: string, to: string) {
  return to === "/" ? pathname === "/" : pathname === to || pathname.startsWith(`${to}/`);
}

/** Barra lateral de iconos; al pasar el mouse se expande sobre el contenido y muestra los nombres. */
function Rail({ items }: { items: NavItem[][] }) {
  const { pathname } = useLocation();
  const [expanded, setExpanded] = React.useState(false);
  return (
    <div className="relative hidden w-[68px] shrink-0 lg:block">
      <motion.nav
        aria-label="Principal"
        onMouseEnter={() => setExpanded(true)}
        onMouseLeave={() => setExpanded(false)}
        onFocus={() => setExpanded(true)}
        onBlur={(e) => { if (!e.currentTarget.contains(e.relatedTarget as Node)) setExpanded(false); }}
        animate={{ width: expanded ? 216 : 68 }}
        transition={SPRING}
        className={cn(
          "absolute inset-y-0 left-0 z-30 flex flex-col gap-1 overflow-hidden border-r border-line bg-surface px-3 py-3",
          expanded && "shadow-pop",
        )}
      >
        {items.map((group, gi) => (
          <React.Fragment key={gi}>
            {gi > 0 ? <span className="mx-2 my-2 h-px bg-line" aria-hidden /> : null}
            {group.map((item) => {
              const Icon = item.icon;
              const active = isActive(pathname, item.to);
              return (
                <NavLink
                  key={item.to}
                  to={item.to}
                  end={item.to === "/"}
                  aria-label={item.label}
                  className={cn(
                    "group relative flex h-11 items-center gap-3 rounded-xl px-[13px] text-sm transition-colors",
                    active ? "font-medium text-ink" : "text-ink-2 hover:text-ink",
                  )}
                >
                  {active ? (
                    <motion.span layoutId="rail-active" transition={SPRING} className="absolute inset-0 rounded-xl bg-hover" aria-hidden>
                      <span className="absolute inset-y-2.5 left-0 w-[3px] rounded-full bg-accent" />
                    </motion.span>
                  ) : (
                    <span className="absolute inset-0 rounded-xl bg-hover opacity-0 transition-opacity group-hover:opacity-60" aria-hidden />
                  )}
                  <Icon className="relative z-10 size-[18px] shrink-0 transition-transform duration-200 group-hover:scale-110" />
                  <AnimatePresence>
                    {expanded ? (
                      <motion.span
                        initial={{ opacity: 0, x: -6 }}
                        animate={{ opacity: 1, x: 0 }}
                        exit={{ opacity: 0, x: -6, transition: { duration: 0.1 } }}
                        transition={{ duration: 0.18, delay: 0.04 }}
                        className="relative z-10 whitespace-nowrap"
                      >
                        {item.label}
                      </motion.span>
                    ) : null}
                  </AnimatePresence>
                </NavLink>
              );
            })}
          </React.Fragment>
        ))}
      </motion.nav>
    </div>
  );
}

/** Navegación inferior en el celular (≤ 5 destinos, objetivos de 44 px o más). */
function BottomNav({ items }: { items: NavItem[] }) {
  const { pathname } = useLocation();
  return (
    <nav aria-label="Principal" className="fixed inset-x-0 bottom-0 z-30 border-t border-line bg-surface/90 pb-[env(safe-area-inset-bottom)] backdrop-blur-md lg:hidden">
      <ul className="grid grid-cols-5">
        {items.map((item) => {
          const Icon = item.icon;
          const active = isActive(pathname, item.to);
          return (
            <li key={item.to}>
              <NavLink to={item.to} end={item.to === "/"}
                className={cn("relative flex h-16 flex-col items-center justify-center gap-1 text-[11px]", active ? "font-medium text-ink" : "text-ink-2")}>
                {active ? <motion.span layoutId="bottom-active" transition={SPRING} className="absolute inset-x-3 top-0 h-0.5 rounded-full bg-accent" aria-hidden /> : null}
                <Icon className="size-5" />
                {item.label}
              </NavLink>
            </li>
          );
        })}
      </ul>
    </nav>
  );
}

/** Rutas en camino, con un punto que late. Lleva a Hoy. */
function LivePill() {
  const dashboard = useDashboard();
  const n = dashboard.data?.routes_in_progress;
  if (n == null) return null;
  return (
    <Link to="/" title="Rutas en camino ahora"
      className="hidden h-8 items-center gap-2 rounded-full border border-line bg-surface px-3 text-[13px] text-ink-3 transition-colors hover:border-line-strong hover:text-ink md:inline-flex">
      <span className={cn("size-2 rounded-full", n > 0 ? "live-dot bg-ok" : "bg-line-strong")} aria-hidden />
      <span className="num font-medium text-ink">{n}</span> en camino
    </Link>
  );
}

/** Campana: recálculos pendientes de aprobar. */
function Alerts() {
  const incidents = useIncidents();
  const n = incidents.data?.reroutes.length ?? 0;
  return (
    <Link to="/" aria-label={n ? `${n} recálculos por revisar` : "Sin avisos"} title={n ? `${n} recálculos por revisar` : "Sin avisos"}
      className="relative grid size-9 place-items-center rounded-lg text-ink-2 transition-colors hover:bg-hover hover:text-ink">
      <BellIcon className="size-[18px]" />
      <AnimatePresence>
        {n > 0 ? (
          <motion.span initial={{ scale: 0 }} animate={{ scale: 1 }} exit={{ scale: 0 }} transition={SPRING}
            className="num absolute right-1 top-1 grid h-4 min-w-4 place-items-center rounded-full bg-delivery px-1 text-[10px] font-semibold text-white">
            {n}
          </motion.span>
        ) : null}
      </AnimatePresence>
    </Link>
  );
}

const THEMES: { value: ThemeChoice; label: string; icon: React.ComponentType<{ className?: string }> }[] = [
  { value: "light", label: "Claro", icon: SunIcon },
  { value: "dark", label: "Oscuro", icon: MoonIcon },
  { value: "system", label: "Sistema", icon: MonitorIcon },
];

function ThemeButton({ theme }: { theme: ReturnType<typeof useTheme> }) {
  const Icon = theme.resolved === "dark" ? MoonIcon : SunIcon;
  return (
    <button type="button" onClick={theme.toggle}
      aria-label={theme.resolved === "dark" ? "Cambiar a tema claro" : "Cambiar a tema oscuro"}
      title={theme.resolved === "dark" ? "Tema claro" : "Tema oscuro"}
      className="relative hidden size-9 place-items-center overflow-hidden rounded-lg text-ink-2 transition-colors hover:bg-hover hover:text-ink sm:grid">
      <AnimatePresence mode="wait" initial={false}>
        <motion.span key={theme.resolved} initial={{ y: 14, opacity: 0, rotate: -40 }} animate={{ y: 0, opacity: 1, rotate: 0 }}
          exit={{ y: -14, opacity: 0, rotate: 40 }} transition={{ duration: 0.2 }}>
          <Icon className="size-[18px]" />
        </motion.span>
      </AnimatePresence>
    </button>
  );
}

function UserMenu({ theme, onLogout }: { theme: ReturnType<typeof useTheme>; onLogout: () => void }) {
  const user = useUser();
  const initials = user.full_name.split(" ").map((w) => w[0]).slice(0, 2).join("").toUpperCase();
  const itemClass = "flex h-9 cursor-pointer select-none items-center gap-2.5 rounded-md px-2.5 text-[13px] text-ink-3 outline-none data-[highlighted]:bg-hover data-[highlighted]:text-ink";
  return (
    <DropdownMenu.Root>
      <DropdownMenu.Trigger aria-label="Menú de usuario"
        className="flex h-9 items-center gap-2 rounded-full pl-0.5 pr-1 transition-colors hover:bg-hover data-[state=open]:bg-hover sm:pr-2.5">
        <span className="grid size-8 place-items-center rounded-full bg-accent-soft text-xs font-semibold text-accent">{initials}</span>
        <span className="hidden text-left leading-tight sm:block">
          <span className="block text-[13px] font-medium">{user.full_name.split(" ")[0]}</span>
          <span className="block text-[11px] text-ink-2">{user.role_label}</span>
        </span>
      </DropdownMenu.Trigger>
      <DropdownMenu.Portal>
        <DropdownMenu.Content align="end" sideOffset={8}
          className="z-50 w-60 rounded-xl border border-line bg-elevated p-1.5 shadow-pop data-[state=open]:animate-in data-[state=open]:fade-in-0 data-[state=open]:zoom-in-95 data-[state=open]:slide-in-from-top-1 data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=closed]:zoom-out-95">
          <div className="px-2.5 pb-2 pt-1.5">
            <p className="truncate text-[13px] font-medium">{user.full_name}</p>
            <p className="text-xs text-ink-2">{user.role_label}</p>
          </div>
          <DropdownMenu.Separator className="my-1 h-px bg-line" />
          <DropdownMenu.Label className="px-2.5 pb-1 pt-1.5 text-[11px] font-medium uppercase tracking-wide text-ink-2">Tema</DropdownMenu.Label>
          <DropdownMenu.RadioGroup value={theme.choice} onValueChange={(v) => theme.set(v as ThemeChoice)}>
            {THEMES.map((t) => (
              <DropdownMenu.RadioItem key={t.value} value={t.value} className={itemClass}>
                <t.icon className="size-4" /> {t.label}
                <DropdownMenu.ItemIndicator className="ml-auto size-1.5 rounded-full bg-accent" />
              </DropdownMenu.RadioItem>
            ))}
          </DropdownMenu.RadioGroup>
          {user.role === "admin" ? (
            <>
              <DropdownMenu.Separator className="my-1 h-px bg-line" />
              <DropdownMenu.Item asChild className={itemClass}>
                <Link to="/configuracion"><SettingsIcon className="size-4" /> Configuración</Link>
              </DropdownMenu.Item>
            </>
          ) : null}
          <DropdownMenu.Separator className="my-1 h-px bg-line" />
          <DropdownMenu.Item onSelect={onLogout} className={cn(itemClass, "data-[highlighted]:text-err")}>
            <LogOutIcon className="size-4" /> Cerrar sesión
          </DropdownMenu.Item>
        </DropdownMenu.Content>
      </DropdownMenu.Portal>
    </DropdownMenu.Root>
  );
}

/** Nombre de la sección actual para la barra superior. */
function sectionLabel(pathname: string) {
  return [...MAIN, ...ANALYSIS].find((i) => isActive(pathname, i.to))?.label ?? "";
}

export function AppShell() {
  const user = useUser();
  const logout = useLogout();
  const navigate = useNavigate();
  const location = useLocation();
  const theme = useTheme();
  const [paletteOpen, setPaletteOpen] = React.useState(false);

  const visible = (items: NavItem[]) => items.filter((i) => !i.adminOnly || user.role === "admin");
  const network = useNetwork();
  const sampleData = network.data ? !isRealData(network.data.data_source) : false;
  const doLogout = () => logout.mutate(undefined, { onSettled: () => navigate("/login", { replace: true }) });

  // ⌘K / Ctrl+K abre la búsqueda global
  React.useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setPaletteOpen((o) => !o);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  const commands: Command[] = [
    ...visible([...MAIN, ...ANALYSIS]).map((i) => ({ id: i.to, group: "Ir a", label: i.label, icon: i.icon, run: () => navigate(i.to) })),
    { id: "lab", group: "Ir a", label: "Laboratorio: Dijkstra vs A*", icon: FlaskConicalIcon, keywords: "algoritmos comparar", run: () => navigate("/analisis/laboratorio") },
    { id: "traffic", group: "Ir a", label: "Tráfico por hora", icon: FlaskConicalIcon, keywords: "franjas congestion", run: () => navigate("/analisis/trafico") },
    { id: "reports", group: "Ir a", label: "Resultados de experimentos", icon: FlaskConicalIcon, keywords: "reportes tesis", run: () => navigate("/analisis/reportes") },
    {
      id: "theme", group: "Acciones", label: theme.resolved === "dark" ? "Cambiar a tema claro" : "Cambiar a tema oscuro",
      icon: theme.resolved === "dark" ? SunIcon : MoonIcon, keywords: "modo oscuro claro tema", run: theme.toggle,
    },
    { id: "logout", group: "Acciones", label: "Cerrar sesión", icon: LogOutIcon, keywords: "salir", run: doLogout },
  ];

  return (
    <div className="flex h-full flex-col">
      <header className="sticky top-0 z-40 flex h-14 shrink-0 items-center gap-3 border-b border-line bg-surface/85 px-3 backdrop-blur-md sm:px-4">
        <Link to="/" className="flex items-center gap-2.5 rounded-lg pr-1 lg:w-[52px] lg:justify-center lg:pr-0" aria-label="enruta, ir a Hoy">
          <LogoMark />
        </Link>
        <div className="flex min-w-0 items-center gap-2 text-sm">
          <span className="font-semibold tracking-tight">enruta</span>
          <span className="text-line-strong" aria-hidden>/</span>
          <AnimatePresence mode="wait" initial={false}>
            <motion.span key={sectionLabel(location.pathname)} initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -6 }} transition={{ duration: 0.16 }} className="truncate text-ink-2">
              {sectionLabel(location.pathname)}
            </motion.span>
          </AnimatePresence>
        </div>

        <div className="flex-1" />

        <button type="button" onClick={() => setPaletteOpen(true)}
          className="flex h-9 items-center gap-2 rounded-lg border border-line bg-bg px-2.5 text-[13px] text-ink-2 transition-colors hover:border-line-strong hover:text-ink sm:w-64"
          aria-label="Buscar o ir a… (Ctrl+K)">
          <SearchIcon className="size-4 shrink-0" />
          <span className="hidden sm:inline">Buscar o ir a…</span>
          <kbd className="num ml-auto hidden rounded border border-line bg-surface px-1.5 text-[11px] sm:inline">Ctrl K</kbd>
        </button>

        {sampleData ? (
          <span className="hidden items-center gap-1.5 text-xs text-ink-2 xl:inline-flex"
            title="Tramos estimados y tráfico sintético: sirven para probar, no son resultados de la tesis. Para datos reales: preparar --google">
            <span className="size-1.5 rounded-full bg-warn" aria-hidden /> Datos de ejemplo
          </span>
        ) : null}
        <LivePill />
        <Alerts />
        <ThemeButton theme={theme} />
        <UserMenu theme={theme} onLogout={doLogout} />
      </header>

      <div className="flex min-h-0 flex-1">
        <Rail items={[visible(MAIN), visible(ANALYSIS)]} />
        <main className="min-w-0 flex-1 overflow-y-auto pb-20 lg:pb-0">
          {/* Análisis anima solo su contenido (sus pestañas quedan fijas) */}
          <PageTransition key={location.pathname.startsWith("/analisis") ? "/analisis" : location.pathname} className="min-h-full">
            <Outlet />
          </PageTransition>
        </main>
      </div>

      <BottomNav items={[...MAIN, ANALYSIS[0]]} />
      <CommandPalette open={paletteOpen} onOpenChange={setPaletteOpen} commands={commands} />
    </div>
  );
}
