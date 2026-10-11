import { useQuery } from "@tanstack/react-query";
import { Check } from "lucide-react";
import { useParams } from "react-router";
import { Stagger, StaggerItem } from "@/components/ui/motion";
import { Spinner } from "@/components/ui/misc";
import { api, ApiError } from "@/lib/api";
import {
  formatStepDate, formatWindow, isFinal, statusHint, statusTone, stepStates, TRACKING_REFRESH_MS, visibleSteps,
  type TrackingData, type Tone,
} from "@/lib/tracking";
import { cn } from "@/lib/utils";

/** Seguimiento pÃºblico del pedido (A3, RUT-71): sin sesiÃ³n, sin AppShell, celular primero. */

const TONE_TEXT: Record<Tone, string> = { ok: "text-ok", err: "text-err", accent: "text-accent", muted: "text-ink" };

function Brand() {
  return (
    <div className="flex items-center gap-1.5">
      <span className="size-2.5 rounded-full bg-delivery" aria-hidden />
      <span className="text-[15px] font-semibold tracking-tight text-ink">enruta</span>
    </div>
  );
}

function Shell({ children }: { children: React.ReactNode }) {
  return (
    <div className="min-h-dvh bg-bg text-ink">
      <main className="mx-auto flex w-full max-w-md flex-col gap-6 px-4 py-6 sm:py-10">
        <Brand />
        {children}
      </main>
    </div>
  );
}

function Timeline({ data }: { data: TrackingData }) {
  const steps = visibleSteps(data.timeline);
  const states = stepStates(steps);
  return (
    <Stagger as="ol" className="flex flex-col" aria-label="Avance del pedido">
      {steps.map((step, i) => {
        const state = states[i];
        const last = i === steps.length - 1;
        const failed = step.key === "failed";
        return (
          <StaggerItem as="li" key={step.key} className="relative flex gap-3 pb-6 last:pb-0">
            {!last && (
              <span
                aria-hidden
                className={cn("absolute left-[11px] top-6 bottom-0 w-px", state === "done" ? "bg-ok" : "bg-line-strong")}
              />
            )}
            <span
              aria-hidden
              className={cn(
                "relative z-10 mt-0.5 grid size-6 shrink-0 place-items-center rounded-full border",
                state === "done" && !failed && "border-ok bg-ok text-on-ink",
                state === "done" && failed && "border-err bg-err text-on-ink",
                state === "current" && "border-accent bg-surface",
                state === "todo" && "border-line-strong bg-surface",
              )}
            >
              {state === "done" ? <Check className="size-3.5" strokeWidth={3} /> : state === "current" ? <span className="live-dot size-2 rounded-full bg-accent" /> : null}
            </span>
            <div className="min-w-0">
              <p className={cn("text-[15px] font-medium leading-6", state === "todo" ? "text-ink-2" : "text-ink")}>{step.label}</p>
              {step.at && <p className="num text-xs text-ink-2">{formatStepDate(step.at)}</p>}
            </div>
          </StaggerItem>
        );
      })}
    </Stagger>
  );
}

function Details({ data }: { data: TrackingData }) {
  const window = formatWindow(data.window);
  const place = [data.place.municipality, data.place.region && `RegiÃ³n ${data.place.region}`].filter(Boolean).join(" Â· ");
  return (
    <div className="flex flex-col gap-4">
      <div className="rounded-xl border border-line bg-surface p-4">
        <p className="text-xs text-ink-2">Pedido</p>
        <p className="num text-lg font-medium">{data.code}</p>
        <div className="mt-3">
          <p className={cn("text-3xl font-semibold tracking-tight", TONE_TEXT[statusTone(data.status)])}>{data.status_label}</p>
          {statusHint(data) && <p className="mt-1 text-sm text-ink-3">{statusHint(data)}</p>}
        </div>
        {window && (
          <div className="mt-4 border-t border-line pt-3">
            <p className="text-xs text-ink-2">Llegada estimada</p>
            <p className="num text-2xl font-medium">{window}</p>
          </div>
        )}
        {place && <p className="mt-3 text-xs text-ink-2">Destino: {place}</p>}
      </div>
      <div className="rounded-xl border border-line bg-surface p-4">
        <Timeline data={data} />
      </div>
    </div>
  );
}

export function TrackingPage() {
  const { token = "" } = useParams();
  const query = useQuery({
    queryKey: ["public-tracking", token],
    queryFn: () => api<TrackingData>(`/api/public/tracking/${encodeURIComponent(token)}/`),
    retry: (count, error) => !(error instanceof ApiError && error.status === 404) && count < 2,
    refetchInterval: (q) => (q.state.data && isFinal(q.state.data.status) ? false : TRACKING_REFRESH_MS),
  });

  if (query.isPending) {
    return (
      <Shell>
        <Spinner />
      </Shell>
    );
  }
  if (query.isError || !query.data) {
    const missing = query.error instanceof ApiError && query.error.status === 404;
    return (
      <Shell>
        <div className="rounded-xl border border-line bg-surface p-5">
          <p className="text-lg font-medium">{missing ? "No encontramos ese pedido" : "No pudimos cargar el seguimiento"}</p>
          <p className="mt-1 text-sm text-ink-3">
            {missing ? "Revisa que el enlace sea el del correo que te enviamos." : "Intenta de nuevo en unos minutos."}
          </p>
        </div>
      </Shell>
    );
  }
  return (
    <Shell>
      <Details data={query.data} />
      <p className="text-center text-xs text-ink-2">Esta pÃ¡gina se actualiza sola cada minuto.</p>
    </Shell>
  );
}
