import { animate, motion, useInView, useReducedMotion, type HTMLMotionProps, type Variants } from "motion/react";
import * as React from "react";
import { cn } from "@/lib/utils";
import type { LatLng } from "@/lib/geo";
import { interpolatePosition } from "@/lib/positionMath";

/** Movimiento del GPS entre lecturas, sin extrapolar y respetando movimiento reducido. */
export function useAnimatedPosition(target: LatLng, sampleKey: string): LatLng {
  const reduce = useReducedMotion();
  const [point, setPoint] = React.useState(target);
  const current = React.useRef(target);
  React.useEffect(() => {
    const from = current.current;
    if (reduce) {
      current.current = target;
      setPoint(target);
      return;
    }
    const start = performance.now();
    let frame = 0;
    function step(now: number) {
      const progress = Math.min(1, (now - start) / 1200);
      const next = interpolatePosition(from, target, progress);
      current.current = next;
      setPoint(next);
      if (progress < 1) frame = requestAnimationFrame(step);
    }
    frame = requestAnimationFrame(step);
    return () => cancelAnimationFrame(frame);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [target.lat, target.lng, sampleKey, reduce]);
  return reduce ? target : point;
}

/*
 Primitivas de animación compartidas. Reglas (design-system/enruta/MASTER.md):
 - Una o dos cosas animadas por vista; el resto quieto.
 - Entradas 200–350 ms con salida suave; nada de rebote en tablas de datos.
 - Con "reducir movimiento" todo aparece en su estado final (MotionConfig en App.tsx).
*/

export const EASE = [0.22, 1, 0.36, 1] as const;
export const SPRING = { type: "spring", stiffness: 420, damping: 34, mass: 0.8 } as const;

/** Entrada de página: sube 8 px y aparece. AppShell la usa con key = ruta. */
export function PageTransition({ children, className }: { children: React.ReactNode; className?: string }) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.28, ease: EASE }}
      className={className}
    >
      {children}
    </motion.div>
  );
}

const staggerParent: Variants = {
  hidden: {},
  show: { transition: { staggerChildren: 0.045, delayChildren: 0.04 } },
};
const staggerChild: Variants = {
  hidden: { opacity: 0, y: 6 },
  show: { opacity: 1, y: 0, transition: { duration: 0.26, ease: EASE } },
};

/** Lista o grilla cuyos hijos (StaggerItem) entran en cascada. `as` = etiqueta (ul, div…). */
export function Stagger({ as = "div", className, children, ...props }:
  { as?: "div" | "ul" | "ol" | "section"; className?: string; children: React.ReactNode } & Omit<HTMLMotionProps<"div">, "children">) {
  const Comp = motion[as] as typeof motion.div;
  return (
    <Comp variants={staggerParent} initial="hidden" animate="show" className={className} {...props}>
      {children}
    </Comp>
  );
}

export function StaggerItem({ as = "div", className, children, ...props }:
  { as?: "div" | "li"; className?: string; children: React.ReactNode } & Omit<HTMLMotionProps<"div">, "children">) {
  const Comp = motion[as] as typeof motion.div;
  return (
    <Comp variants={staggerChild} className={className} {...props}>
      {children}
    </Comp>
  );
}

/** Aparece al entrar en pantalla (una sola vez). Para secciones bajo el pliegue. */
export function Reveal({ children, className, delay = 0 }: { children: React.ReactNode; className?: string; delay?: number }) {
  const ref = React.useRef<HTMLDivElement>(null);
  const inView = useInView(ref, { once: true, margin: "-40px" });
  return (
    <motion.div
      ref={ref}
      initial={{ opacity: 0, y: 12 }}
      animate={inView ? { opacity: 1, y: 0 } : undefined}
      transition={{ duration: 0.35, ease: EASE, delay }}
      className={className}
    >
      {children}
    </motion.div>
  );
}

/**
 Número que cuenta hasta su valor cuando cambia (KPIs, minutos, km).
 Si el valor no es número (p. ej. "—") lo muestra tal cual.
*/
export function AnimatedNumber({ value, decimals = 0, className, format }: {
  value: number | string | null | undefined;
  decimals?: number;
  className?: string;
  format?: (n: number) => string;
}) {
  const reduce = useReducedMotion();
  const ref = React.useRef<HTMLSpanElement>(null);
  const prev = React.useRef<number>(0);
  const isNum = typeof value === "number" && Number.isFinite(value);
  const show = React.useCallback(
    (n: number) => (format ? format(n) : n.toLocaleString("es-GT", { minimumFractionDigits: decimals, maximumFractionDigits: decimals })),
    [decimals, format],
  );

  React.useEffect(() => {
    if (!isNum || !ref.current) return;
    const to = value as number;
    if (reduce) {
      ref.current.textContent = show(to);
      prev.current = to;
      return;
    }
    const controls = animate(prev.current, to, {
      duration: 0.7,
      ease: EASE,
      onUpdate: (n) => {
        if (ref.current) ref.current.textContent = show(n);
      },
    });
    prev.current = to;
    return () => controls.stop();
  }, [isNum, value, reduce, show]);

  if (!isNum) return <span className={className}>{value ?? "—"}</span>;
  return <span ref={ref} className={cn("num", className)}>{show(reduce ? (value as number) : prev.current)}</span>;
}

/** Tarjeta con profundidad sutil. `interactive` = se eleva al pasar el mouse (si es clicable). */
export function Card({ className, interactive, children, ...props }:
  React.HTMLAttributes<HTMLDivElement> & { interactive?: boolean }) {
  return (
    <div
      className={cn(
        "rounded-xl border border-line bg-surface shadow-card",
        interactive && "transition-[box-shadow,transform,border-color] duration-200 hover:-translate-y-0.5 hover:border-line-strong hover:shadow-lift",
        className,
      )}
      {...props}
    >
      {children}
    </div>
  );
}

/** Bloque de carga con brillo. Reserva el espacio del contenido para que nada salte. */
export function Skeleton({ className }: { className?: string }) {
  return <div className={cn("skeleton", className)} aria-hidden />;
}

/**
 Pestañas con indicador que se desliza (layoutId). `id` debe ser único por grupo.
 Sirve para filtros locales; para pestañas que son rutas usa NavTabs.
*/
export function AnimatedTabs<T extends string>({ id, value, onChange, options, label, className }: {
  id: string;
  value: T;
  onChange: (value: T) => void;
  options: { value: T; label: React.ReactNode }[];
  label: string;
  className?: string;
}) {
  return (
    <div role="tablist" aria-label={label} className={cn("relative inline-flex w-fit gap-1 rounded-lg bg-hover p-1", className)}>
      {options.map((o) => {
        const active = o.value === value;
        return (
          <button
            key={o.value}
            type="button"
            role="tab"
            aria-selected={active}
            onClick={() => onChange(o.value)}
            className={cn("relative h-8 shrink-0 whitespace-nowrap rounded-md px-3 text-[13px] font-medium transition-colors", active ? "text-ink" : "text-ink-2 hover:text-ink")}
          >
            {active ? (
              <motion.span layoutId={`tabs-${id}`} transition={SPRING} className="absolute inset-0 rounded-md bg-surface shadow-card" aria-hidden />
            ) : null}
            <span className="relative z-10 inline-flex items-center gap-1.5">{o.label}</span>
          </button>
        );
      })}
    </div>
  );
}
