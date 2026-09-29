import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import * as React from "react";
import { api, ApiError } from "./api";
import type { Role, User } from "./types";

const SESSION_KEY = ["session"];

async function fetchSession(): Promise<User | null> {
  try {
    const data = await api<{ user: User }>("/api/auth/session/");
    return data.user;
  } catch (error) {
    if (error instanceof ApiError && error.status === 401) return null;
    throw error;
  }
}

export function useSession() {
  return useQuery({ queryKey: SESSION_KEY, queryFn: fetchSession, staleTime: 5 * 60 * 1000, retry: false });
}

export function useLogin() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (credentials: { username: string; password: string }) =>
      api<{ user: User }>("/api/auth/login/", { method: "POST", body: credentials }),
    onSuccess: (data) => client.setQueryData(SESSION_KEY, data.user),
  });
}

/** Entrar sin contraseña como el despachador o el conductor de demostración (si el servidor lo permite). */
export function useDemoLogin() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (role: "dispatcher" | "driver") => api<{ user: User }>("/api/auth/demo/", { method: "POST", body: { role } }),
    onSuccess: (data) => client.setQueryData(SESSION_KEY, data.user),
  });
}

export function useLogout() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: () => api("/api/auth/logout/", { method: "POST", body: {} }),
    onSettled: () => {
      client.clear();
      client.setQueryData(SESSION_KEY, null);
    },
  });
}

/** Pantalla de inicio según el rol: el conductor tiene su propia vista móvil. */
export function homeFor(role: Role): string {
  return role === "driver" ? "/conductor" : "/";
}

export const UserContext = React.createContext<User | null>(null);

export function useUser(): User {
  const user = React.useContext(UserContext);
  if (!user) throw new Error("useUser fuera de una ruta con sesión");
  return user;
}
