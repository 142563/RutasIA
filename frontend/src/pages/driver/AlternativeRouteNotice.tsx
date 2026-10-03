/**
 * Aviso de ruta alternativa (docs/PLAN.md §8, flujo C).
 *
 * Si el sistema encontró una ruta más rápida por un incidente, el conductor la ve aquí
 * con "Aceptar" y "Mantener mi ruta". Se consulta cada 30 s mientras la ruta está en curso.
 */
import { RouteIcon } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { ErrorNote } from "@/components/ui/misc";
import type { DriverRoute } from "@/lib/driver";
import { incidentHeadline, savingLabel, useDecideReroute, useIncidents } from "@/lib/incidents";

export function AlternativeRouteNotice({ route }: { route: Pick<DriverRoute, "id" | "status"> }) {
  const active = route.status === "in_progress" || route.status === "planned";
  const incidents = useIncidents(route.status === "in_progress");
  const decide = useDecideReroute();
  if (!active) return null;

  const proposal = incidents.data?.reroutes.find((r) => r.route_id === route.id);
  if (!proposal) return null;
  const incident = incidents.data?.incidents.find((i) => i.id === proposal.incident_id);

  function onDecide(decision: "accept" | "keep") {
    decide.mutate(
      { id: proposal!.id, decision },
      {
        onSuccess: () => toast.success(decision === "accept" ? "Listo. Ya tienes la ruta nueva." : "Seguirás por tu ruta actual."),
        onError: (error) => toast.error(error.message),
      },
    );
  }

  return (
    <section aria-label="Ruta alternativa" role="alert" className="flex flex-col gap-4 rounded-2xl border border-warn/40 bg-warn/5 p-4">
      <div className="flex items-start gap-3">
        <RouteIcon className="mt-0.5 size-5 shrink-0 text-warn" aria-hidden />
        <div className="flex flex-col gap-1">
          <p className="text-[17px] font-semibold leading-snug tracking-tight">{incidentHeadline(incident)}</p>
          <p className="text-[15px] text-ink-3">
            {proposal.summary || `Hay una ruta más rápida: ${savingLabel(proposal)}`}
          </p>
        </div>
      </div>
      <div className="grid gap-2.5">
        <Button className="h-12 rounded-xl text-[15px]" disabled={decide.isPending} onClick={() => onDecide("accept")}>
          {decide.isPending ? "Un momento…" : "Aceptar"}
        </Button>
        <Button variant="outline" className="h-12 rounded-xl text-[15px]" disabled={decide.isPending} onClick={() => onDecide("keep")}>
          Mantener mi ruta
        </Button>
      </div>
      {decide.isError ? <ErrorNote error={decide.error} /> : null}
    </section>
  );
}
