import { useQuery } from "@tanstack/react-query";
import { SmartphoneIcon, UserRoundIcon } from "lucide-react";
import * as React from "react";
import { Navigate, useLocation, useNavigate } from "react-router";
import { Logo } from "@/components/layout/AppShell";
import { Button } from "@/components/ui/button";
import { Field, Input } from "@/components/ui/field";
import { api } from "@/lib/api";
import { homeFor, useDemoLogin, useLogin, useSession } from "@/lib/auth";
import type { User } from "@/lib/types";

export function LoginPage() {
  const session = useSession();
  const login = useLogin();
  const demo = useDemoLogin();
  const navigate = useNavigate();
  const location = useLocation();
  const [username, setUsername] = React.useState("");
  const [password, setPassword] = React.useState("");
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

  const error = login.error ?? demo.error;

  return (
    <div className="grid min-h-full place-items-center px-4 py-12">
      <div className="w-full max-w-[360px]">
        <Logo />
        <h1 className="mt-8 text-xl font-semibold tracking-tight">Iniciar sesión</h1>
        <p className="mt-1 text-[13px] text-ink-2">Rutas con tráfico para paquetería en Guatemala.</p>

        {config.data?.demo_login ? (
          <div className="mt-6 flex flex-col gap-2">
            <p className="text-xs text-ink-2">Entrar a la demostración</p>
            <div className="grid grid-cols-2 gap-2">
              <Button variant="outline" size="lg" disabled={demo.isPending}
                onClick={() => demo.mutate("dispatcher", { onSuccess: ({ user }) => goHome(user) })}>
                <UserRoundIcon /> Despachador
              </Button>
              <Button variant="outline" size="lg" disabled={demo.isPending}
                onClick={() => demo.mutate("driver", { onSuccess: ({ user }) => goHome(user) })}>
                <SmartphoneIcon /> Conductor
              </Button>
            </div>
            <p className="mt-4 flex items-center gap-3 text-xs text-ink-2">
              <span className="h-px flex-1 bg-line" />o con tu usuario<span className="h-px flex-1 bg-line" />
            </p>
          </div>
        ) : null}

        <form onSubmit={submit} className="mt-6 flex flex-col gap-4">
          <Field label="Usuario" htmlFor="username">
            <Input id="username" autoComplete="username" autoFocus={!config.data?.demo_login} value={username}
              onChange={(e) => setUsername(e.target.value)} required />
          </Field>
          <Field label="Contraseña" htmlFor="password">
            <Input id="password" type="password" autoComplete="current-password" value={password} onChange={(e) => setPassword(e.target.value)} required />
          </Field>
          {error ? <p className="text-[13px] text-err" role="alert">{error.message}</p> : null}
          <Button type="submit" size="lg" disabled={login.isPending}>
            {login.isPending ? "Entrando…" : "Entrar"}
          </Button>
        </form>
      </div>
    </div>
  );
}
