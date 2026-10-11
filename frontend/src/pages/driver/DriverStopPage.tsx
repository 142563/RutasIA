import { CheckIcon, NavigationIcon, PackageCheckIcon, PackageXIcon, PhoneIcon } from "lucide-react";
import { AnimatePresence, motion } from "motion/react";
import * as React from "react";
import { Link, useNavigate, useParams } from "react-router";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/field";
import { EmptyState, ErrorNote } from "@/components/ui/misc";
import { EASE, Skeleton } from "@/components/ui/motion";
import { useUser } from "@/lib/auth";
import { findStop, navigationUrl, REASONS, telUrl, useDriverToday, useUpdateStop } from "@/lib/driver";
import { formatClock } from "@/lib/format";
import { cn } from "@/lib/utils";
import { AnimatedCheck, DriverHeader, DriverPage } from "./parts";
import { ReportIncident } from "./ReportIncident";

const OTHER = "Otro";

type Step = "idle" | "confirm" | "failing";

/** Conductor · Detalle de parada (docs/prototipo/Conductor-Parada.dc.html). */
export function DriverStopPage() {
  const stopId = Number(useParams().stopId);
  const navigate = useNavigate();
  const user = useUser();
  const today = useDriverToday();
  const update = useUpdateStop();
  const [step, setStep] = React.useState<Step>("idle");
  const [choice, setChoice] = React.useState<string | null>(null);
  const [freeText, setFreeText] = React.useState("");
  // Resultado ya registrado: muestra el check animado un momento y regresa a la ruta
  const [saved, setSaved] = React.useState<"delivered" | "failed" | null>(null);
  const timer = React.useRef<ReturnType<typeof setTimeout>>(undefined);
  React.useEffect(() => () => clearTimeout(timer.current), []);

  const found = findStop(today.data, stopId);
  const name = today.data?.driver.name ?? user.full_name ?? user.username;
  const header = <DriverHeader name={name} back={{ to: "/conductor", label: "← Mi ruta" }} />;

  if (today.isPending) {
    return (
      <DriverPage>
        {header}
        <div className="flex flex-col gap-4 px-4 pt-6" role="status" aria-label="Cargando la parada">
          <Skeleton className="h-8 w-2/3" />
          <Skeleton className="h-5 w-full" />
          <Skeleton className="h-14" />
          <Skeleton className="h-14" />
        </div>
      </DriverPage>
    );
  }
  if (today.isError) {
    return (
      <DriverPage>
        {header}
        <div className="flex flex-col gap-3 px-4 pt-6">
          <ErrorNote error={today.error} />
          <Button variant="outline" className="h-12 rounded-xl text-[15px]" onClick={() => today.refetch()}>
            Reintentar
          </Button>
        </div>
      </DriverPage>
    );
  }
  if (!found) {
    return (
      <DriverPage>
        {header}
        <EmptyState title="No encontramos esta parada" action={<Button asChild variant="outline" className="h-12 rounded-xl"><Link to="/conductor">Volver a mi ruta</Link></Button>}>
          Puede que ya no esté en tu ruta de hoy.
        </EmptyState>
      </DriverPage>
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
  const who = stop.recipient || stop.order_code;

  function mark(status: "delivered" | "failed") {
    update.mutate(
      { stopId: stop.id, status, reason: status === "failed" ? reason : undefined },
      {
        onSuccess: () => {
          setSaved(status);
          timer.current = setTimeout(() => navigate("/conductor", { replace: true }), 1300);
        },
        onError: (error) => toast.error(error.message),
      },
    );
  }

  if (saved) {
    return (
      <DriverPage className="items-center justify-center gap-4 px-6 text-center" >
        <AnimatedCheck size={96} tone={saved === "delivered" ? "ok" : "err"} />
        <motion.div
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.3, ease: EASE, delay: 0.5 }}
          role="status"
        >
          <p className="text-2xl font-semibold tracking-tight">{saved === "delivered" ? "Entrega registrada" : "Registrado sin entregar"}</p>
          <p className="mt-1 text-[15px] text-ink-2">{who}</p>
        </motion.div>
      </DriverPage>
    );
  }

  return (
    <DriverPage>
      {header}
      <main className="flex flex-1 flex-col gap-5 px-4 pb-10 pt-5">
        <header className="flex flex-col gap-1.5">
          <div className="flex items-center justify-between gap-3 text-[13px] text-ink-2">
            <span>
              Parada <span className="num">{stop.sequence}</span> de <span className="num">{total}</span>
            </span>
            <span>
              Llegada <span className="num text-[15px] font-medium text-ink">{formatClock(stop.eta)}</span>
            </span>
          </div>
          <h1 className="mt-1 text-[28px] font-semibold leading-tight tracking-tight">{who}</h1>
          <p className="text-base leading-snug text-ink-3">{stop.address}</p>
          <p className="num mt-1 text-xs text-ink-2">{stop.order_code}</p>
        </header>

        <div className="grid grid-cols-2 gap-3">
          <ActionLink href={tel} icon={<PhoneIcon />} label="Llamar" />
          <ActionLink href={nav ? `/conductor/navegar/${stop.id}` : null} icon={<NavigationIcon />} label="Navegar" internal />
        </div>

        {!pending ? (
          <section className="flex items-start gap-3 rounded-xl border border-line bg-surface px-4 py-3.5 shadow-card" aria-live="polite">
            {stop.status === "delivered" ? <PackageCheckIcon className="mt-0.5 size-5 text-ok" aria-hidden /> : <PackageXIcon className="mt-0.5 size-5 text-err" aria-hidden />}
            <div className="flex flex-col gap-0.5">
              <span className={cn("text-[15px] font-medium", stop.status === "delivered" ? "text-ok" : "text-err")}>
                {stop.status === "delivered" ? "Entregado" : "No entregado"}
              </span>
              <span className="text-[13px] text-ink-2">
                Registrado a las <span className="num">{formatClock(stop.delivered_at)}</span>.
                {stop.reason ? ` Motivo: ${stop.reason.toLowerCase()}.` : ""}
              </span>
            </div>
          </section>
        ) : locked ? (
          <p className="text-[13px] text-ink-2">Esta ruta ya no admite cambios.</p>
        ) : route.status === "planned" ? (
          <p className="text-[13px] text-ink-2">Al marcar esta parada, tu ruta se inicia automáticamente.</p>
        ) : null}

        {pending && !locked ? (
          <AnimatePresence mode="wait" initial={false}>
            {step === "idle" ? (
              <motion.div key="idle" {...swap} className="flex flex-col gap-3">
                <Button className="h-14 rounded-xl text-base" disabled={busy} onClick={() => setStep("confirm")}>
                  <CheckIcon aria-hidden /> Entregado
                </Button>
                <Button variant="outline" className="h-14 rounded-xl text-base" disabled={busy} onClick={() => setStep("failing")}>
                  No se pudo entregar
                </Button>
                {route.status === "in_progress" ? <ReportIncident routeId={route.id} /> : null}
              </motion.div>
            ) : step === "confirm" ? (
              <motion.section key="confirm" {...swap} aria-label="Confirmar entrega" className="flex flex-col gap-4 rounded-2xl border border-line bg-surface p-5 shadow-lift">
                <div className="flex flex-col gap-1">
                  <h2 className="text-lg font-semibold tracking-tight">¿Confirmas la entrega?</h2>
                  <p className="text-[15px] text-ink-3">Se la diste a {who}. Esto avisa al despachador.</p>
                </div>
                <div className="grid gap-2.5">
                  <Button className="h-14 rounded-xl text-base" disabled={busy} onClick={() => mark("delivered")}>
                    {busy ? "Registrando…" : "Sí, entregado"}
                  </Button>
                  <Button variant="ghost" className="h-12 rounded-xl text-[15px]" disabled={busy} onClick={() => setStep("idle")}>
                    Volver
                  </Button>
                </div>
              </motion.section>
            ) : (
              <motion.section key="failing" {...swap} className="flex flex-col gap-4" aria-label="Motivo de no entrega">
                <h2 className="text-lg font-semibold tracking-tight">¿Qué pasó?</h2>
                <div role="radiogroup" aria-label="Motivo" className="flex flex-col gap-2">
                  {[...REASONS, OTHER].map((r) => {
                    const on = choice === r;
                    return (
                      <button
                        key={r}
                        type="button"
                        role="radio"
                        aria-checked={on}
                        onClick={() => setChoice(r)}
                        className={cn(
                          "flex min-h-14 items-center gap-3 rounded-xl border px-4 py-2 text-left text-[15px] transition-[border-color,background-color,box-shadow] duration-150",
                          on ? "border-ink bg-surface font-medium shadow-[0_0_0_1px_var(--color-ink)]" : "border-line-strong bg-surface text-ink-3 hover:bg-hover",
                        )}
                      >
                        <span className={cn("flex size-5 shrink-0 items-center justify-center rounded-full border", on ? "border-ink bg-ink text-on-ink" : "border-line-strong")} aria-hidden>
                          {on ? <CheckIcon className="size-3" strokeWidth={3} /> : null}
                        </span>
                        {r}
                      </button>
                    );
                  })}
                </div>
                {choice === OTHER ? (
                  <Textarea
                    value={freeText}
                    maxLength={120}
                    onChange={(e) => setFreeText(e.target.value)}
                    placeholder="Describe brevemente el motivo"
                    aria-label="Motivo"
                    className="text-base"
                  />
                ) : null}
                <div className="grid gap-2.5">
                  <Button className="h-14 rounded-xl text-base" disabled={busy || !reason} onClick={() => mark("failed")}>
                    {busy ? "Registrando…" : "Registrar"}
                  </Button>
                  <Button variant="ghost" className="h-12 rounded-xl text-[15px]" disabled={busy} onClick={() => setStep("idle")}>
                    Cancelar
                  </Button>
                </div>
              </motion.section>
            )}
          </AnimatePresence>
        ) : null}

        {!pending || locked ? (
          <Button asChild variant="outline" className="h-14 rounded-xl text-base">
            <Link to="/conductor">Volver a mi ruta</Link>
          </Button>
        ) : null}
      </main>
    </DriverPage>
  );
}

// Cambio de paso: sale rápido y entra con un leve deslizamiento
const swap = {
  initial: { opacity: 0, y: 10 },
  animate: { opacity: 1, y: 0, transition: { duration: 0.22, ease: EASE } },
  exit: { opacity: 0, y: -6, transition: { duration: 0.12 } },
};

function ActionLink({ href, icon, label, internal }: { href: string | null; icon: React.ReactNode; label: string; internal?: boolean }) {
  if (!href) {
    return (
      <Button variant="outline" className="h-14 rounded-xl text-base" disabled>
        {icon}
        {label}
      </Button>
    );
  }
  return (
    <Button asChild variant="outline" className="h-14 rounded-xl text-base">
      {internal ? (
        <Link to={href}>{icon}{label}</Link>
      ) : (
        <a href={href}>{icon}{label}</a>
      )}
    </Button>
  );
}
