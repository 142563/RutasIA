import * as React from "react";
import { Navigate, useLocation, useNavigate } from "react-router";
import { Logo } from "@/components/layout/AppShell";
import { Button } from "@/components/ui/button";
import { Field, Input } from "@/components/ui/field";
import { homeFor, useLogin, useSession } from "@/lib/auth";

export function LoginPage() {
  const session = useSession();
  const login = useLogin();
  const navigate = useNavigate();
  const location = useLocation();
  const [username, setUsername] = React.useState("");
  const [password, setPassword] = React.useState("");

  if (session.data) return <Navigate to={homeFor(session.data.role)} replace />;

  function submit(event: React.FormEvent) {
    event.preventDefault();
    login.mutate(
      { username, password },
      {
        onSuccess: ({ user }) => {
          const from = (location.state as { from?: string } | null)?.from;
          navigate(user.role === "driver" ? "/conductor" : from ?? "/", { replace: true });
        },
      },
    );
  }

  return (
    <div className="grid min-h-full place-items-center px-4 py-12">
      <div className="w-full max-w-[360px]">
        <Logo />
        <h1 className="mt-8 text-xl font-semibold tracking-tight">Iniciar sesión</h1>
        <p className="mt-1 text-[13px] text-ink-2">Rutas con tráfico para paquetería en Guatemala.</p>
        <form onSubmit={submit} className="mt-6 flex flex-col gap-4">
          <Field label="Usuario" htmlFor="username">
            <Input id="username" autoComplete="username" autoFocus value={username} onChange={(e) => setUsername(e.target.value)} required />
          </Field>
          <Field label="Contraseña" htmlFor="password">
            <Input id="password" type="password" autoComplete="current-password" value={password} onChange={(e) => setPassword(e.target.value)} required />
          </Field>
          {login.error ? <p className="text-[13px] text-err" role="alert">{login.error.message}</p> : null}
          <Button type="submit" size="lg" disabled={login.isPending}>
            {login.isPending ? "Entrando…" : "Entrar"}
          </Button>
        </form>
      </div>
    </div>
  );
}
