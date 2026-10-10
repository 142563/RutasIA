import { useQuery } from "@tanstack/react-query";
import { ArrowRightIcon, EyeIcon, EyeOffIcon, LoaderCircleIcon, SmartphoneIcon, UserRoundIcon } from "lucide-react";
import { motion } from "motion/react";
import * as React from "react";
import { Navigate, useLocation, useNavigate } from "react-router";
import { Logo } from "@/components/layout/AppShell";
import { Button } from "@/components/ui/button";
import { Field, Input } from "@/components/ui/field";
import { EASE, Stagger, StaggerItem } from "@/components/ui/motion";
import { api } from "@/lib/api";
import { homeFor, useDemoLogin, useLogin, useSession } from "@/lib/auth";
import type { User } from "@/lib/types";
import { cn } from "@/lib/utils";

export function LoginPage() {
  const session = useSession();
  const login = useLogin();
  const demo = useDemoLogin();
  const navigate = useNavigate();
  const location = useLocation();
  const [username, setUsername] = React.useState("");
  const [password, setPassword] = React.useState("");
  const [showPassword, setShowPassword] = React.useState(false);
  const config = useQuery({
    queryKey: ["config"],
    queryFn: () => api<{ demo_login: boolean }>("/api/config/"),
    staleTime: Infinity,
  });

  if (session.data) return <Navigate to={homeFor(session.data.role)} replace />;

  function goHome(user: User) {
    const from = (location.state as { from?: string } | null)?.from;
    navigate(user.role === "driver" ? "/conductor" : from ?? "/", { replace: true });
  }

  function submit(event: React.FormEvent) {
    event.preventDefault();
    login.mutate({ username, password }, { onSuccess: ({ user }) => goHome(user) });
  }

  function enterDemo(role: "dispatcher" | "driver") {
    demo.mutate(role, { onSuccess: ({ user }) => goHome(user) });
  }

  const formError = login.error?.message ?? null;
  const demoError = demo.error?.message ?? null;
  const showDemo = !!config.data?.demo_login;

  return (
    <div className="grid min-h-full bg-bg lg:grid-cols-[minmax(0,1.1fr)_minmax(0,1fr)]">
      <BrandPanel />

      <main className="flex items-center justify-center px-5 py-10 sm:px-10">
        <Stagger className="flex w-full max-w-[400px] flex-col">
          <StaggerItem className="lg:hidden">
            <Logo />
          </StaggerItem>
          <StaggerItem>
            <h1 className="mt-8 text-[28px] font-semibold leading-tight tracking-tight lg:mt-0">Bienvenido de nuevo</h1>
            <p className="mt-1.5 text-[15px] text-ink-2">Entra para planificar y seguir tus rutas.</p>
          </StaggerItem>

          {showDemo ? (
            <StaggerItem className="mt-7 flex flex-col gap-2.5">
              <p className="text-xs font-medium uppercase tracking-wide text-ink-2">Probar la demostración</p>
              <div className="grid gap-2.5 sm:grid-cols-2">
                <DemoOption
                  icon={<UserRoundIcon />}
                  title="Despachador"
                  description="Planifica pedidos y mira las rutas en vivo."
                  pending={demo.isPending && demo.variables === "dispatcher"}
                  disabled={demo.isPending}
                  onClick={() => enterDemo("dispatcher")}
                />
                <DemoOption
                  icon={<SmartphoneIcon />}
                  title="Conductor"
                  description="Vista del celular: paradas y navegación."
                  pending={demo.isPending && demo.variables === "driver"}
                  disabled={demo.isPending}
                  onClick={() => enterDemo("driver")}
                />
              </div>
              {demoError ? <p className="text-[13px] text-err" role="alert">{demoError}</p> : null}
              <p className="mt-3 flex items-center gap-3 text-xs text-ink-2" aria-hidden>
                <span className="h-px flex-1 bg-line" />o con tu usuario<span className="h-px flex-1 bg-line" />
              </p>
            </StaggerItem>
          ) : null}

          <StaggerItem>
            <form onSubmit={submit} className={cn("flex flex-col gap-4", showDemo ? "mt-3" : "mt-7")}>
              <Field label="Usuario" htmlFor="username">
                <Input
                  id="username"
                  className="h-11 text-[15px]"
                  autoComplete="username"
                  autoFocus={!showDemo}
                  value={username}
                  aria-invalid={!!formError}
                  onChange={(e) => setUsername(e.target.value)}
                  required
                />
              </Field>
              <Field label="Contraseña" htmlFor="password" error={formError}>
                <div className="relative">
                  <Input
                    id="password"
                    className="h-11 pr-11 text-[15px]"
                    type={showPassword ? "text" : "password"}
                    autoComplete="current-password"
                    value={password}
                    aria-invalid={!!formError}
                    aria-describedby={formError ? "login-error" : undefined}
                    onChange={(e) => setPassword(e.target.value)}
                    required
                  />
                  <button
                    type="button"
                    onClick={() => setShowPassword((v) => !v)}
                    aria-label={showPassword ? "Ocultar contraseña" : "Mostrar contraseña"}
                    aria-pressed={showPassword}
                    className="absolute right-1 top-1/2 flex size-9 -translate-y-1/2 items-center justify-center rounded-md text-ink-2 transition-colors hover:bg-hover hover:text-ink"
                  >
                    {showPassword ? <EyeOffIcon className="size-4" /> : <EyeIcon className="size-4" />}
                  </button>
                </div>
              </Field>
              {formError ? <span id="login-error" role="alert" className="sr-only">{formError}</span> : null}
              <Button type="submit" size="lg" className="h-11" disabled={login.isPending}>
                {login.isPending ? <><LoaderCircleIcon className="animate-spin" aria-hidden /> Entrando…</> : <>Entrar <ArrowRightIcon aria-hidden /></>}
              </Button>
            </form>
          </StaggerItem>
        </Stagger>
      </main>
    </div>
  );
}

/** Opción grande de la demostración: icono, rol y una línea de qué se ve. */
function DemoOption({ icon, title, description, pending, disabled, onClick }: {
  icon: React.ReactNode;
  title: string;
  description: string;
  pending: boolean;
  disabled: boolean;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      className="group flex flex-col items-start gap-3 rounded-xl border border-line bg-surface p-4 text-left shadow-card transition-[box-shadow,transform,border-color] duration-200 hover:-translate-y-0.5 hover:border-line-strong hover:shadow-lift active:translate-y-0 disabled:pointer-events-none disabled:opacity-60"
    >
      <span className="flex w-full items-center justify-between">
        <span className="flex size-10 items-center justify-center rounded-lg bg-accent-soft text-accent [&_svg]:size-5">{icon}</span>
        {pending ? (
          <LoaderCircleIcon className="size-4 animate-spin text-ink-2" aria-label="Entrando" />
        ) : (
          <ArrowRightIcon className="size-4 text-ink-2 transition-transform group-hover:translate-x-0.5 group-hover:text-ink" aria-hidden />
        )}
      </span>
      <span className="flex flex-col gap-0.5">
        <span className="text-[15px] font-semibold tracking-tight">{title}</span>
        <span className="text-[13px] leading-snug text-ink-2">{description}</span>
      </span>
    </button>
  );
}

/** Panel de identidad (solo escritorio): una frase de valor y una ruta que se dibuja sola sobre una red de puntos. */
function BrandPanel() {
  return (
    <aside className="relative hidden flex-col justify-between overflow-hidden border-r border-line bg-surface p-10 lg:flex xl:p-14" aria-hidden>
      <Logo />

      <RouteIllustration />

      <div className="relative z-10 max-w-md">
        <motion.h2
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5, ease: EASE, delay: 0.2 }}
          className="text-[34px] font-semibold leading-[1.1] tracking-tight xl:text-[40px]"
        >
          La ruta más rápida,
          <br />
          <span className="text-ink-2">no la más corta.</span>
        </motion.h2>
        <motion.p
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ duration: 0.5, delay: 0.5 }}
          className="mt-4 text-[15px] leading-relaxed text-ink-3"
        >
          enruta calcula cada tramo con el tráfico de la hora para que tus paquetes lleguen antes a cualquier punto de Guatemala.
        </motion.p>
      </div>
    </aside>
  );
}

// Red de puntos y una ruta que se traza entre dos de ellos
const DOTS: [number, number][] = [
  [60, 90], [150, 60], [250, 100], [340, 70], [420, 120], [90, 190], [190, 170], [290, 200], [380, 220],
  [450, 260], [60, 290], [140, 320], [240, 300], [330, 340], [420, 380], [100, 420], [200, 410], [300, 450], [390, 470],
];
const ROUTE = "M90 190 C130 190 150 170 190 170 S250 190 290 200 S340 270 330 340 S350 420 300 450";
const TRAFFIC = "M290 200 C320 215 335 270 330 340";

function RouteIllustration() {
  return (
    <svg viewBox="0 0 500 520" className="pointer-events-none absolute inset-0 m-auto h-[88%] w-auto max-w-full" fill="none">
      {/* Conexiones tenues de la red */}
      <g stroke="var(--color-line-strong)" strokeWidth="1">
        {[[0, 1], [1, 2], [2, 3], [3, 4], [5, 6], [6, 7], [7, 8], [8, 9], [10, 11], [11, 12], [12, 13], [13, 14], [15, 16], [16, 17], [17, 18],
          [0, 5], [5, 10], [10, 15], [2, 7], [7, 12], [12, 17], [4, 9], [9, 14], [14, 18], [1, 6], [6, 11], [11, 16], [3, 8], [8, 13]].map(([a, b]) => (
          <line key={`${a}-${b}`} x1={DOTS[a][0]} y1={DOTS[a][1]} x2={DOTS[b][0]} y2={DOTS[b][1]} />
        ))}
      </g>
      {DOTS.map(([x, y], i) => (
        <circle key={i} cx={x} cy={y} r="3" fill="var(--color-line-strong)" />
      ))}

      {/* Tramo con tráfico (debajo de la ruta) */}
      <motion.path
        d={TRAFFIC} stroke="var(--color-delivery)" strokeWidth="10" strokeLinecap="round" opacity="0.25"
        initial={{ pathLength: 0 }} animate={{ pathLength: 1 }} transition={{ duration: 0.8, ease: EASE, delay: 1.6 }}
      />
      {/* La ruta elegida, dibujándose */}
      <motion.path
        d={ROUTE} stroke="var(--color-ink)" strokeWidth="4" strokeLinecap="round" strokeLinejoin="round"
        initial={{ pathLength: 0 }} animate={{ pathLength: 1 }} transition={{ duration: 2.2, ease: EASE, delay: 0.4 }}
      />

      {/* Origen y destino */}
      <circle cx="90" cy="190" r="7" fill="var(--color-ink)" />
      <circle cx="90" cy="190" r="3" fill="var(--color-surface)" />
      <motion.g initial={{ scale: 0, opacity: 0 }} animate={{ scale: 1, opacity: 1 }} transition={{ delay: 2.5, duration: 0.4, ease: EASE }} style={{ transformOrigin: "300px 450px" }}>
        <circle cx="300" cy="450" r="16" fill="var(--color-delivery)" opacity="0.2" />
        <circle cx="300" cy="450" r="8" fill="var(--color-delivery)" />
      </motion.g>
    </svg>
  );
}
