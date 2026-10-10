/**
 * Aviso de ruta alternativa (docs/PLAN.md §8, flujo C).
 *
 * Si el sistema encontró una ruta más rápida por un incidente, el conductor la ve aquí
 * con "Aceptar" y "Mantener mi ruta". Se consulta cada 30 s mientras la ruta está en curso.
 */
import { RouteIcon } from "lucide-react";
import { AnimatePresence, motion } from "motion/react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { ErrorNote } from "@/components/ui/misc";
import { EASE } from "@/components/ui/motion";
import type { DriverRoute } from "@/lib/driver";
import { incidentHeadline, savingLabel, useDecideReroute, useIncidents } from "@/lib/incidents";

export function AlternativeRouteNotice({ route }: { route: Pick<DriverRoute, "id" | "status"> }) {
  const active = route.status === "in_progress" || route.status === "planned";
  const incidents = useIncidents(route.status === "in_progress");
  const decide = useDecideReroute();

  const proposal = active ? incidents.data?.reroutes.find((r) => r.route_id === route.id) : undefined;
  const incident = proposal ? incidents.data?.incidents.find((i) => i.id === proposal.incident_id) : undefined;

  function onDecide(decision: "accept" | "keep") {
    if (!proposal) return;
    decide.mutate(
      { id: proposal.id, decision },
      {
        onSuccess: () => toast.success(decision === "accept" ? "Listo. Ya tienes la ruta nueva." : "Seguirás por tu ruta actual."),
        onError: (error) => toast.error(error.message),
      },
    );
  }

  return (
    <AnimatePresence>
      {proposal ? (
        <motion.section
          key={proposal.id}
          aria-label="Ruta alternativa"
          role="alert"
          initial={{ opacity: 0, y: -28 }}
          animate={{ opacity: 1, y: 0, transition: { duration: 0.4, ease: EASE } }}
          exit={{ opacity: 0, y: -16, transition: { duration: 0.2 } }}
          className="flex flex-col gap-4 rounded-2xl border border-delivery/50 bg-delivery/10 p-4"
        >
          <div className="flex items-start gap-3">
            <span className="flex size-10 shrink-0 items-center justify-center rounded-full bg-delivery/20 text-delivery">
              <RouteIcon className="size-5" aria-hidden />
            </span>
            <div className="flex min-w-0 flex-col gap-1">
              <p className="text-xs font-medium uppercase tracking-wide text-ink-3">Hay una ruta más rápida</p>
              <p className="text-[17px] font-semibold leading-snug tracking-tight">{incidentHeadline(incident)}</p>
            </div>
          </div>

          {/* Comparación: tu ruta contra la propuesta, con el ahorro como cifra */}
          <div className="grid grid-cols-2 gap-px overflow-hidden rounded-xl border border-delivery/30 bg-delivery/30">
            <div className="flex flex-col gap-0.5 bg-surface px-3 py-2.5">
              <span className="text-xs text-ink-2">Tu ruta</span>
              <span className="text-[15px] font-medium">{proposal.current_blocked ? "Tramo cerrado" : "La actual"}</span>
            </div>
            <div className="flex flex-col gap-0.5 bg-surface px-3 py-2.5">
              <span className="text-xs text-ink-2">Alternativa</span>
              <span className="num text-[22px] font-semibold leading-tight text-delivery">{savingLabel(proposal)}</span>
            </div>
          </div>
          {proposal.summary ? <p className="text-[15px] text-ink-3">{proposal.summary}</p> : null}

          <div className="grid gap-2.5">
            <Button className="h-14 rounded-xl text-base" disabled={decide.isPending} onClick={() => onDecide("accept")}>
              {decide.isPending ? "Un momento…" : "Aceptar ruta nueva"}
            </Button>
            <Button variant="outline" className="h-12 rounded-xl text-[15px]" disabled={decide.isPending} onClick={() => onDecide("keep")}>
              Mantener mi ruta
            </Button>
          </div>
          {decide.isError ? <ErrorNote error={decide.error} /> : null}
        </motion.section>
      ) : null}
    </AnimatePresence>
  );
}
