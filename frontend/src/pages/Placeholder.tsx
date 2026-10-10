import { ArrowLeftIcon, CalendarClockIcon } from "lucide-react";
import { motion } from "motion/react";
import { Link } from "react-router";
import { Button } from "@/components/ui/button";
import { EmptyState, PageHeader } from "@/components/ui/misc";
import { EASE } from "@/components/ui/motion";

/** Secciones que llegan más adelante en el cronograma (docs/PLAN.md §10). */
export function ComingSoonPage({ title, when, description }: { title: string; when: string; description: string }) {
  return (
    <div>
      <PageHeader title={title} />
      <EmptyState icon={<CalendarClockIcon />} title={`Disponible en la ${when}`}>
        {description}
      </EmptyState>
    </div>
  );
}

/** 404: una ruta que se traza y se corta en seco, con el destino al otro lado. */
export function NotFoundPage() {
  return (
    <div className="flex flex-col items-center justify-center gap-6 px-6 py-16 text-center">
      <svg viewBox="0 0 320 140" className="h-auto w-full max-w-[320px]" fill="none" aria-hidden>
        {/* Tramo recorrido */}
        <motion.path
          d="M24 100 C70 100 80 40 130 40 S180 80 196 70"
          stroke="var(--color-ink)" strokeWidth="4" strokeLinecap="round"
          initial={{ pathLength: 0 }} animate={{ pathLength: 1 }} transition={{ duration: 1.2, ease: EASE, delay: 0.2 }}
        />
        {/* Tramo que no existe */}
        <motion.path
          d="M222 58 C250 40 262 44 286 40"
          stroke="var(--color-line-strong)" strokeWidth="4" strokeLinecap="round" strokeDasharray="2 10"
          initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: 1.2 }}
        />
        <circle cx="24" cy="100" r="7" fill="var(--color-ink)" />
        <circle cx="24" cy="100" r="3" fill="var(--color-surface)" />
        {/* Corte */}
        <motion.g initial={{ scale: 0 }} animate={{ scale: 1 }} transition={{ delay: 1.3, duration: 0.3, ease: EASE }} style={{ transformOrigin: "209px 64px" }}>
          <path d="M202 56l14 16M216 56l-14 16" stroke="var(--color-err)" strokeWidth="4" strokeLinecap="round" />
        </motion.g>
        <circle cx="290" cy="40" r="8" fill="var(--color-delivery)" opacity="0.35" />
      </svg>

      <motion.div
        initial={{ opacity: 0, y: 8 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.35, ease: EASE, delay: 0.3 }}
        className="flex flex-col items-center gap-2"
      >
        <p className="num text-sm text-ink-2">Error 404</p>
        <h1 className="text-2xl font-semibold tracking-tight">Esta ruta no existe</h1>
        <p className="max-w-sm text-[15px] text-ink-2">Te saliste del mapa. Revisa la dirección o vuelve al inicio.</p>
        <Button asChild className="mt-3 h-11 px-5 text-[15px]">
          <Link to="/"><ArrowLeftIcon aria-hidden /> Volver al inicio</Link>
        </Button>
      </motion.div>
    </div>
  );
}
