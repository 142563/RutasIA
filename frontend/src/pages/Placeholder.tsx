import { CalendarClockIcon, CompassIcon } from "lucide-react";
import { Link } from "react-router";
import { Button } from "@/components/ui/button";
import { EmptyState, PageHeader } from "@/components/ui/misc";

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

export function NotFoundPage() {
  return (
    <EmptyState
      icon={<CompassIcon />}
      title="Esta página no existe"
      action={<Button asChild variant="outline"><Link to="/">Ir al inicio</Link></Button>}
    >
      Revisa la dirección o vuelve al inicio.
    </EmptyState>
  );
}
