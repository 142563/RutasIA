import { ArrowLeftIcon, NavigationIcon, PhoneIcon } from "lucide-react";
import * as React from "react";
import { Link, useNavigate, useParams } from "react-router";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/field";
import { EmptyState, ErrorNote, Spinner } from "@/components/ui/misc";
import { findStop, navigationUrl, REASONS, telUrl, useDriverToday, useUpdateStop } from "@/lib/driver";
import { formatClock } from "@/lib/format";
import { cn } from "@/lib/utils";

const OTHER = "Otro";

/** Conductor · Detalle de parada (docs/prototipo/Conductor-Parada.dc.html). */
export function DriverStopPage() {
  const stopId = Number(useParams().stopId);
  const navigate = useNavigate();
  const today = useDriverToday();
  const update = useUpdateStop();
  const [failing, setFailing] = React.useState(false);
  const [choice, setChoice] = React.useState<string | null>(null);
  const [freeText, setFreeText] = React.useState("");

  const found = findStop(today.data, stopId);
  const back = (
    <Link to="/conductor" className="inline-flex h-11 items-center gap-1.5 text-[13px] text-ink-2 hover:text-ink">
      <ArrowLeftIcon className="size-4" aria-hidden /> Mi ruta
    </Link>
  );

  if (today.isPending) {
    return (
      <Shell>
        {back}
        <div className="flex justify-center py-16">
          <Spinner label="Cargando la parada…" />
        </div>
      </Shell>
    );
  }
  if (today.isError) {
    return (
      <Shell>
        {back}
        <ErrorNote error={today.error} />
        <Button variant="outline" className="h-12" onClick={() => today.refetch()}>
          Reintentar
        </Button>
      </Shell>
    );
  }
  if (!found) {
    return (
      <Shell>
        {back}
        <EmptyState title="No encontramos esta parada">Puede que ya no esté en tu ruta de hoy.</EmptyState>
      </Shell>
    );
  }

  const { route, stop } = found;
  const total = route.stops.length;
  const pending = stop.status === "pending";
  const locked = route.status === "completed" || route.status === "canceled";
  const nav = navigationUrl(stop);
  const tel = telUrl(stop.phone);
  const reason = choice === OTHER ? freeText.trim() : (choice ?? "");
  const busy = update.isPending;

  function mark(status: "delivered" | "failed") {
    update.mutate(
      { stopId: stop.id, status, reason: status === "failed" ? reason : undefined },
      {
        onSuccess: () => {
          toast.success(status === "delivered" ? "Entrega registrada." : "Registrado como no entregado.");
          navigate("/conductor", { replace: true });
        },
        onError: (error) => toast.error(error.message),
      },
    );
  }

  return (
    <Shell>
      {back}
      <header className="flex flex-col gap-1.5">
        <span className="text-[13px] text-ink-2">
          Parada {stop.sequence} de {total}
        </span>
        <span className="text-[13px] text-ink-2">
          Llegada <span className="num">{formatClock(stop.eta)}</span>
        </span>
        <h1 className="mt-1 text-[26px] font-semibold leading-tight tracking-tight">{stop.recipient || stop.order_code}</h1>
        <p className="text-[15px] text-ink-3">{stop.address}</p>
        <p className="num mt-1 text-xs text-ink-2">{stop.order_code}</p>
      </header>

      <div className="grid grid-cols-2 gap-3">
        <ActionLink href={tel} icon={<PhoneIcon />} label="Llamar" />
        <ActionLink href={nav} icon={<NavigationIcon />} label="Navegar" external />
      </div>

      {!pending ? (
        <section className="flex flex-col gap-1 rounded-xl border border-line bg-bg px-4 py-3.5" aria-live="polite">
          <span className={cn("text-[15px] font-medium", stop.status === "delivered" ? "text-ok" : "text-err")}>
            {stop.status === "delivered" ? "Entregado" : "No entregado"}
          </span>
          <span className="text-[13px] text-ink-2">
            Registrado a las <span className="num">{formatClock(stop.delivered_at)}</span>.
            {stop.reason ? ` Motivo: ${stop.reason.toLowerCase()}.` : ""}
          </span>
        </section>
      ) : locked ? (
        <p className="text-[13px] text-ink-2">Esta ruta ya no admite cambios.</p>
      ) : route.status === "planned" ? (
        <p className="text-[13px] text-ink-2">Al marcar esta parada, tu ruta se inicia automáticamente.</p>
      ) : null}

      {pending && !locked && !failing ? (
        <div className="flex flex-col gap-3">
          <Button className="h-12 rounded-xl text-[15px]" disabled={busy} onClick={() => mark("delivered")}>
            {busy ? "Registrando…" : "Marcar como entregado"}
          </Button>
          <Button variant="outline" className="h-12 rounded-xl text-[15px]" disabled={busy} onClick={() => setFailing(true)}>
            No se pudo entregar
          </Button>
        </div>
      ) : null}

      {pending && !locked && failing ? (
        <section className="flex flex-col gap-4" aria-label="Motivo de no entrega">
          <h2 className="text-[15px] font-semibold">¿Qué pasó?</h2>
          <div role="radiogroup" aria-label="Motivo" className="flex flex-col">
            {[...REASONS, OTHER].map((r) => (
              <button
                key={r}
                type="button"
                role="radio"
                aria-checked={choice === r}
                onClick={() => setChoice(r)}
                className="flex min-h-12 items-center gap-3 border-b border-line py-2 text-left text-[15px]"
              >
                <span
                  className={cn("size-[18px] shrink-0 rounded-full", choice === r ? "border-[6px] border-ink" : "border-[1.5px] border-line-strong")}
                  aria-hidden
                />
                {r}
              </button>
            ))}
          </div>
          {choice === OTHER ? (
            <Textarea
              value={freeText}
              maxLength={120}
              onChange={(e) => setFreeText(e.target.value)}
              placeholder="Describe brevemente el motivo"
              aria-label="Motivo"
            />
          ) : null}
          <div className="flex flex-col gap-3">
            <Button className="h-12 rounded-xl text-[15px]" disabled={busy || !reason} onClick={() => mark("failed")}>
              {busy ? "Registrando…" : "Registrar"}
            </Button>
            <Button variant="ghost" className="h-12 rounded-xl text-[15px]" disabled={busy} onClick={() => setFailing(false)}>
              Cancelar
            </Button>
          </div>
        </section>
      ) : null}

      {!pending || locked ? (
        <Button asChild variant="outline" className="h-12 rounded-xl text-[15px]">
          <Link to="/conductor">Volver a mi ruta</Link>
        </Button>
      ) : null}
    </Shell>
  );
}

function Shell({ children }: { children: React.ReactNode }) {
  return <div className="mx-auto flex min-h-dvh w-full max-w-[480px] flex-col gap-6 bg-surface px-6 pb-10 pt-4">{children}</div>;
}

function ActionLink({ href, icon, label, external }: { href: string | null; icon: React.ReactNode; label: string; external?: boolean }) {
  if (!href) {
    return (
      <Button variant="outline" className="h-12 rounded-xl text-[15px]" disabled>
        {icon}
        {label}
      </Button>
    );
  }
  return (
    <Button asChild variant="outline" className="h-12 rounded-xl text-[15px]">
      <a href={href} {...(external ? { target: "_blank", rel: "noopener noreferrer" } : {})}>
        {icon}
        {label}
      </a>
    </Button>
  );
}
