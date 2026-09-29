import { LoaderCircleIcon } from "lucide-react";
import * as React from "react";
import { cn } from "@/lib/utils";

/** Estado como punto + texto (sin "pastillas" de color, §9). */
export function StatusDot({ color, children, className }: { color: string; children: React.ReactNode; className?: string }) {
  return (
    <span className={cn("inline-flex items-center gap-2 text-[13px] text-ink-3", className)}>
      <span className="size-2 shrink-0 rounded-full" style={{ background: color }} aria-hidden />
      {children}
    </span>
  );
}

export function Spinner({ className, label = "Cargando…" }: { className?: string; label?: string }) {
  return (
    <span className={cn("inline-flex items-center gap-2 text-sm text-ink-2", className)} role="status">
      <LoaderCircleIcon className="size-4 animate-spin" aria-hidden />
      {label}
    </span>
  );
}

export function EmptyState({ icon, title, children, action }: {
  icon?: React.ReactNode;
  title: string;
  children?: React.ReactNode;
  action?: React.ReactNode;
}) {
  return (
    <div className="flex flex-col items-center justify-center gap-2 px-6 py-16 text-center">
      {icon ? <div className="mb-1 text-ink-2 [&_svg]:size-6">{icon}</div> : null}
      <p className="text-sm font-medium">{title}</p>
      {children ? <div className="max-w-sm text-[13px] text-ink-2">{children}</div> : null}
      {action ? <div className="mt-3">{action}</div> : null}
    </div>
  );
}

export function ErrorNote({ error }: { error: unknown }) {
  const message = error instanceof Error ? error.message : "Ocurrió un error inesperado.";
  return (
    <p className="rounded-lg border border-err/20 bg-err/5 px-3 py-2 text-[13px] text-err" role="alert">
      {message}
    </p>
  );
}

/** Control segmentado (p. ej. Más corta | Más rápida). */
export function Segmented<T extends string>({ value, onChange, options, label }: {
  value: T;
  onChange: (value: T) => void;
  options: { value: T; label: string }[];
  label: string;
}) {
  return (
    <div role="radiogroup" aria-label={label} className="inline-flex w-fit rounded-lg border border-line bg-bg p-0.5">
      {options.map((o) => (
        <button
          key={o.value}
          type="button"
          role="radio"
          aria-checked={value === o.value}
          onClick={() => onChange(o.value)}
          className={cn(
            "h-8 rounded-md px-3 text-[13px] font-medium text-ink-2 transition-colors",
            value === o.value ? "bg-surface text-ink shadow-[0_0_0_1px_var(--color-line)]" : "hover:text-ink",
          )}
        >
          {o.label}
        </button>
      ))}
    </div>
  );
}

/** Cifra grande con etiqueta (tiempo, km, nodos…), siempre en Geist Mono. */
export function Metric({ label, value, hint, className }: { label: string; value: React.ReactNode; hint?: React.ReactNode; className?: string }) {
  return (
    <div className={cn("flex flex-col gap-1", className)}>
      <span className="text-xs text-ink-2">{label}</span>
      <span className="num text-2xl font-medium tracking-tight">{value}</span>
      {hint ? <span className="text-xs text-ink-2">{hint}</span> : null}
    </div>
  );
}

export function PageHeader({ title, subtitle, actions }: { title: string; subtitle?: React.ReactNode; actions?: React.ReactNode }) {
  return (
    <header className="flex flex-wrap items-end justify-between gap-4 border-b border-line px-6 py-5 lg:px-8">
      <div>
        <h1 className="text-xl font-semibold tracking-tight">{title}</h1>
        {subtitle ? <p className="mt-1 text-[13px] text-ink-2">{subtitle}</p> : null}
      </div>
      {actions ? <div className="flex items-center gap-2">{actions}</div> : null}
    </header>
  );
}
