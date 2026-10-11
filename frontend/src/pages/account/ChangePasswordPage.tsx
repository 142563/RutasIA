import { useMutation, useQueryClient } from "@tanstack/react-query";
import { CheckIcon, CircleIcon, EyeIcon, EyeOffIcon, LoaderCircleIcon } from "lucide-react";
import * as React from "react";
import { useNavigate } from "react-router";
import { toast } from "sonner";
import { Logo } from "@/components/layout/AppShell";
import { Button } from "@/components/ui/button";
import { Field, Input } from "@/components/ui/field";
import { Stagger, StaggerItem } from "@/components/ui/motion";
import { api } from "@/lib/api";
import { homeFor, useLogout, useSession } from "@/lib/auth";
import type { User } from "@/lib/types";

const MIN_LENGTH = 10;

/** Cambio obligatorio de la contraseña temporal (A2, RUT-70). */
export function ChangePasswordPage() {
  const session = useSession();
  const client = useQueryClient();
  const navigate = useNavigate();
  const logout = useLogout();
  const [current, setCurrent] = React.useState("");
  const [next, setNext] = React.useState("");
  const [confirm, setConfirm] = React.useState("");
  const [show, setShow] = React.useState(false);
  const [submitted, setSubmitted] = React.useState(false);

  const change = useMutation({
    mutationFn: () => api("/api/auth/password/", { method: "POST", body: { current_password: current, new_password: next } }),
    onSuccess: async () => {
      // Quita la marca en la sesión en caché para que RequireSession deje pasar, y la confirma con el servidor
      client.setQueryData<User | null>(["session"], (user) => (user ? { ...user, must_change_password: false } : user));
      await client.invalidateQueries({ queryKey: ["session"] });
      toast.success("Contraseña actualizada");
      navigate(homeFor(session.data?.role ?? "dispatcher"), { replace: true });
    },
  });

  const rules = [
    { ok: next.length >= MIN_LENGTH, label: `Al menos ${MIN_LENGTH} caracteres` },
    { ok: next.length > 0 && next !== current, label: "Distinta de la temporal" },
  ];
  const errors = {
    current: current ? null : "Escribe la contraseña temporal que recibiste.",
    next: rules.every((r) => r.ok) ? null : "La nueva contraseña no cumple las reglas.",
    confirm: confirm === next ? null : "Las contraseñas no coinciden.",
  };
  // El servidor valida además contra contraseñas comunes o parecidas al usuario; su mensaje va junto al campo que corresponde
  const serverError = change.error?.message ?? null;
  const serverOnCurrent = !!serverError && /actual/i.test(serverError);

  function submit(event: React.FormEvent) {
    event.preventDefault();
    setSubmitted(true);
    if (errors.current || errors.next || errors.confirm) return;
    change.mutate();
  }

  const type = show ? "text" : "password";
  const toggle = (
    <button
      type="button"
      onClick={() => setShow((v) => !v)}
      aria-label={show ? "Ocultar contraseñas" : "Mostrar contraseñas"}
      aria-pressed={show}
      className="flex h-8 items-center gap-1.5 rounded-md px-2 text-xs text-ink-2 transition-colors hover:bg-hover hover:text-ink"
    >
      {show ? <EyeOffIcon className="size-4" /> : <EyeIcon className="size-4" />}
      {show ? "Ocultar" : "Mostrar"}
    </button>
  );

  return (
    <main className="flex min-h-full items-center justify-center bg-bg px-5 py-10 sm:px-10">
      <Stagger className="flex w-full max-w-[420px] flex-col">
        <StaggerItem><Logo /></StaggerItem>
        <StaggerItem>
          <h1 className="mt-8 text-[28px] font-semibold leading-tight tracking-tight">Crea tu contraseña</h1>
          <p className="mt-1.5 text-[15px] text-ink-2">
            {session.data ? `Hola ${session.data.full_name}. ` : ""}Entraste con una contraseña temporal. Elige una propia para continuar.
          </p>
        </StaggerItem>
        <StaggerItem>
          <form onSubmit={submit} className="mt-7 flex flex-col gap-4" noValidate>
            <Field label="Contraseña temporal" htmlFor="cp-current" error={(submitted && errors.current) || (serverOnCurrent ? serverError : null)}>
              <Input id="cp-current" className="h-11 text-[15px]" type={type} autoComplete="current-password" autoFocus
                value={current} onChange={(e) => setCurrent(e.target.value)} aria-invalid={(submitted && !!errors.current) || serverOnCurrent} />
            </Field>
            <Field label="Contraseña nueva" htmlFor="cp-next" error={(submitted && errors.next) || (!serverOnCurrent ? serverError : null)}>
              <Input id="cp-next" className="h-11 text-[15px]" type={type} autoComplete="new-password"
                value={next} onChange={(e) => setNext(e.target.value)} aria-invalid={(submitted && !!errors.next) || (!!serverError && !serverOnCurrent)}
                aria-describedby="cp-rules" />
            </Field>
            <ul id="cp-rules" className="-mt-2 flex flex-col gap-1 text-xs">
              {rules.map((rule) => (
                <li key={rule.label} className={rule.ok ? "flex items-center gap-1.5 text-ok" : "flex items-center gap-1.5 text-ink-2"}>
                  {rule.ok ? <CheckIcon className="size-3.5" aria-hidden /> : <CircleIcon className="size-3.5" aria-hidden />}
                  {rule.label}
                </li>
              ))}
              <li className="flex items-center gap-1.5 text-ink-2">
                <CircleIcon className="size-3.5" aria-hidden />
                Evita contraseñas comunes o parecidas a tu usuario
              </li>
            </ul>
            <Field label="Confirma la contraseña nueva" htmlFor="cp-confirm" error={submitted ? errors.confirm : null}>
              <Input id="cp-confirm" className="h-11 text-[15px]" type={type} autoComplete="new-password"
                value={confirm} onChange={(e) => setConfirm(e.target.value)} aria-invalid={submitted && !!errors.confirm} />
            </Field>
            <div className="flex justify-end">{toggle}</div>
            <Button type="submit" size="lg" className="h-11" disabled={change.isPending}>
              {change.isPending ? <><LoaderCircleIcon className="animate-spin" aria-hidden /> Guardando…</> : "Guardar y continuar"}
            </Button>
            <button
              type="button"
              onClick={() => logout.mutate(undefined, { onSuccess: () => navigate("/login", { replace: true }) })}
              className="self-center text-[13px] text-ink-2 underline-offset-4 hover:text-ink hover:underline"
            >
              Salir
            </button>
          </form>
        </StaggerItem>
      </Stagger>
    </main>
  );
}
