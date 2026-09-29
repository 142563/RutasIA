import { NavLink, Outlet } from "react-router";
import { cn } from "@/lib/utils";

/** Todo lo de la tesis en un solo lugar: los algoritmos, el tráfico y los resultados. */
const TABS = [
  { to: "laboratorio", label: "Dijkstra vs A*" },
  { to: "trafico", label: "Tráfico por hora" },
  { to: "reportes", label: "Resultados" },
];

export function AnalysisLayout() {
  return (
    <div className="flex min-h-full flex-col">
      <nav aria-label="Análisis" className="flex gap-1 overflow-x-auto border-b border-line px-6 lg:px-8">
        {TABS.map((t) => (
          <NavLink
            key={t.to}
            to={t.to}
            className={({ isActive }) =>
              cn(
                "-mb-px flex h-11 items-center whitespace-nowrap border-b-2 px-2.5 text-[13px] text-ink-2 transition-colors hover:text-ink",
                isActive ? "border-ink font-medium text-ink" : "border-transparent",
              )
            }
          >
            {t.label}
          </NavLink>
        ))}
      </nav>
      <div className="flex-1">
        <Outlet />
      </div>
    </div>
  );
}
