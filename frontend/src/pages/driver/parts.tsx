import { LogOutIcon } from "lucide-react";
import { motion } from "motion/react";
import { DropdownMenu } from "radix-ui";
import * as React from "react";
import { Link } from "react-router";
import { LogoMark } from "@/components/layout/AppShell";
import { EASE } from "@/components/ui/motion";
import { useLogout } from "@/lib/auth";
import { cn } from "@/lib/utils";

/*
 Piezas locales de la vista del conductor (celular, en la carretera).
 Objetivos táctiles de 48 px o más; el color nunca es la única señal.
*/

/** Contenedor de página móvil: una columna de 480 px sin AppShell. */
export function DriverPage({ children, className }: { children: React.ReactNode; className?: string }) {
  return <div className={cn("mx-auto flex min-h-dvh w-full max-w-[480px] flex-col bg-bg", className)}>{children}</div>;
}

/** Encabezado fijo: marca, nombre y menú de sesión. `back` lo reemplaza por un enlace de regreso. */
export function DriverHeader({ name, back }: { name: string; back?: { to: string; label: string } }) {
  const logout = useLogout();
  const initial = name.trim().charAt(0).toUpperCase() || "?";
  return (
    <header className="sticky top-0 z-20 flex h-14 items-center gap-3 border-b border-line bg-surface px-4">
      {back ? (
        <Link to={back.to} className="-ml-2 inline-flex h-12 items-center gap-1.5 rounded-lg px-2 text-[15px] font-medium text-ink-3 hover:text-ink">
          {back.label}
        </Link>
      ) : (
        <div className="flex items-center gap-2">
          <LogoMark size={26} />
          <span className="text-[17px] font-semibold tracking-tight">enruta</span>
        </div>
      )}
      <DropdownMenu.Root>
        <DropdownMenu.Trigger asChild>
          <button
            type="button"
            aria-label={`Menú de ${name}`}
            className="ml-auto flex h-12 items-center gap-2 rounded-full pl-3 pr-1 text-sm text-ink-3 transition-colors hover:bg-hover"
          >
            <span className="max-w-[120px] truncate">{name.split(" ")[0]}</span>
            <span className="flex size-9 items-center justify-center rounded-full bg-ink text-sm font-semibold text-on-ink">{initial}</span>
          </button>
        </DropdownMenu.Trigger>
        <DropdownMenu.Portal>
          <DropdownMenu.Content
            align="end"
            sideOffset={6}
            className="z-50 min-w-48 rounded-xl border border-line bg-elevated p-1.5 shadow-pop data-[state=open]:animate-in data-[state=open]:fade-in-0 data-[state=open]:zoom-in-95"
          >
            <div className="px-3 py-2">
              <p className="truncate text-sm font-medium">{name}</p>
              <p className="text-xs text-ink-2">Conductor</p>
            </div>
            <DropdownMenu.Separator className="my-1 h-px bg-line" />
            <DropdownMenu.Item
              disabled={logout.isPending}
              onSelect={() => logout.mutate()}
              className="flex h-12 cursor-pointer items-center gap-2.5 rounded-lg px-3 text-[15px] text-ink outline-none data-[highlighted]:bg-hover"
            >
              <LogOutIcon className="size-4" aria-hidden /> Cerrar sesión
            </DropdownMenu.Item>
          </DropdownMenu.Content>
        </DropdownMenu.Portal>
      </DropdownMenu.Root>
    </header>
  );
}

/** Check que se dibuja solo (círculo y palomita con pathLength). `tone` = ok o err (con X). */
export function AnimatedCheck({ size = 72, tone = "ok" }: { size?: number; tone?: "ok" | "err" }) {
  const color = tone === "ok" ? "var(--color-ok)" : "var(--color-err)";
  return (
    <svg width={size} height={size} viewBox="0 0 72 72" fill="none" aria-hidden>
      <motion.circle
        cx="36" cy="36" r="31" stroke={color} strokeWidth="4" strokeLinecap="round"
        initial={{ pathLength: 0, opacity: 0 }} animate={{ pathLength: 1, opacity: 1 }}
        transition={{ duration: 0.5, ease: EASE }}
      />
      {tone === "ok" ? (
        <motion.path
          d="M22 37l9 9 19-21" stroke={color} strokeWidth="5" strokeLinecap="round" strokeLinejoin="round"
          initial={{ pathLength: 0 }} animate={{ pathLength: 1 }}
          transition={{ duration: 0.4, ease: EASE, delay: 0.35 }}
        />
      ) : (
        <motion.path
          d="M25 25l22 22M47 25L25 47" stroke={color} strokeWidth="5" strokeLinecap="round"
          initial={{ pathLength: 0 }} animate={{ pathLength: 1 }}
          transition={{ duration: 0.4, ease: EASE, delay: 0.35 }}
        />
      )}
    </svg>
  );
}

/** Barra de progreso del día: se llena al cargar y cuando cambia. */
export function ProgressBar({ done, total, percent }: { done: number; total: number; percent: number }) {
  return (
    <div
      role="progressbar"
      aria-label="Entregas completadas"
      aria-valuemin={0}
      aria-valuemax={total}
      aria-valuenow={done}
      className="h-2 overflow-hidden rounded-full bg-line"
    >
      <motion.div
        className="h-full rounded-full bg-ink"
        initial={{ width: 0 }}
        animate={{ width: `${percent}%` }}
        transition={{ duration: 0.7, ease: EASE }}
      />
    </div>
  );
}
