import type { QueryClient } from "@tanstack/react-query";
import type { User } from "./types";

export const SESSION_KEY = ["session"];

/** Cancela consultas pendientes y descarta datos privados de la cuenta anterior. */
export function replaceSession(client: QueryClient, user: User | null) {
  const session = client.getQueryCache().find({ queryKey: SESSION_KEY, exact: true });
  void client.cancelQueries();
  // Se conserva esta consulta para que los observadores de sesión reciban el cambio.
  client.removeQueries({ predicate: (query) => query !== session });
  client.getMutationCache().clear();
  client.setQueryData(SESSION_KEY, user);
}
