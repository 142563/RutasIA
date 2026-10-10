import * as React from "react";

/** Tema claro, oscuro o el del sistema. Se guarda solo en este navegador. */
export type ThemeChoice = "light" | "dark" | "system";

const KEY = "enruta-theme";
const listeners = new Set<() => void>();

function readChoice(): ThemeChoice {
  try {
    const v = localStorage.getItem(KEY);
    return v === "light" || v === "dark" ? v : "system";
  } catch {
    return "system";
  }
}

function systemDark() {
  return typeof matchMedia === "function" && matchMedia("(prefers-color-scheme: dark)").matches;
}

export function resolveTheme(choice: ThemeChoice, prefersDark: boolean): "light" | "dark" {
  return choice === "system" ? (prefersDark ? "dark" : "light") : choice;
}

// Estado compartido por toda la app (barra, toasts, gráficas): una sola fuente
let state = { choice: readChoice(), resolved: resolveTheme(readChoice(), systemDark()) };

function commit(choice: ThemeChoice) {
  state = { choice, resolved: resolveTheme(choice, systemDark()) };
  document.documentElement.classList.toggle("dark", state.resolved === "dark");
  listeners.forEach((l) => l());
}

if (typeof matchMedia === "function") {
  matchMedia("(prefers-color-scheme: dark)").addEventListener("change", () => {
    if (state.choice === "system") commit("system");
  });
}

export function setTheme(choice: ThemeChoice) {
  try {
    if (choice === "system") localStorage.removeItem(KEY);
    else localStorage.setItem(KEY, choice);
  } catch {
    // Sin almacenamiento el tema dura solo esta visita
  }
  commit(choice);
}

function subscribe(listener: () => void) {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

/** Hook del tema: la elección, el tema resuelto y cómo cambiarlo. */
export function useTheme() {
  const snap = React.useSyncExternalStore(subscribe, () => state);
  const toggle = React.useCallback(() => setTheme(state.resolved === "dark" ? "light" : "dark"), []);
  return { choice: snap.choice, resolved: snap.resolved, set: setTheme, toggle };
}
