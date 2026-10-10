import { motion } from "motion/react";
import { NavLink, Outlet, useLocation } from "react-router";
import { PageTransition, SPRING } from "@/components/ui/motion";
import { cn } from "@/lib/utils";

/** Todo lo de la tesis en un solo lugar: los algoritmos, el tráfico y los resultados. */
const TABS = [
  { to: "laboratorio", label: "Dijkstra vs A*" },
  { to: "trafico", label: "Tráfico por hora" },
  { to: "reportes", label: "Resultados" },
];

export function AnalysisLayout() {
  const { pathname } = useLocation();
  return (
    <div className="flex min-h-full flex-col">
      <header className="px-6 pt-7 lg:px-8">
        <h1 className="text-2xl font-semibold tracking-tight">Análisis</h1>
        <p className="mt-1 text-[13px] text-ink-2">Los algoritmos, el tráfico y los experimentos que respaldan la tesis.</p>
      </header>
      <nav aria-label="Análisis" className="mt-4 flex gap-1 overflow-x-auto border-b border-line px-6 lg:px-8">
        {TABS.map((t) => (
          <NavLink
            key={t.to}
            to={t.to}
            className={({ isActive }) =>
              cn(
                "relative flex h-11 items-center whitespace-nowrap px-2.5 text-[13px] text-ink-2 transition-colors hover:text-ink",
                isActive && "font-medium text-ink",
              )
            }
          >
            {({ isActive }) => (
              <>
                {t.label}
                {isActive ? (
                  <motion.span layoutId="analysis-tab" transition={SPRING} className="absolute inset-x-1.5 -bottom-px h-0.5 rounded-full bg-ink" aria-hidden />
                ) : null}
              </>
            )}
          </NavLink>
        ))}
      </nav>
      <PageTransition key={pathname} className="flex-1">
        <Outlet />
      </PageTransition>
    </div>
  );
}
