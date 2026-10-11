import { QueryClient, QueryObserver } from "@tanstack/react-query";
import { describe, expect, it } from "vitest";
import { replaceSession, SESSION_KEY } from "./sessionCache";
import type { User } from "./types";

const nextUser: User = { id: 2, username: "otro", full_name: "Otro conductor", role: "driver", role_label: "Conductor", driver_id: 2, must_change_password: false };

describe("replaceSession", () => {
  it.each([nextUser, null])("elimina datos de consultas y mutaciones antes de establecer %s", async (user) => {
    const client = new QueryClient();
    client.setQueryData(SESSION_KEY, { ...nextUser, id: 1 });
    client.setQueryData(["driver-today"], { address: "Dirección privada anterior" });
    client.setQueryData(["orders"], [{ recipient: "Cliente anterior" }]);
    const mutation = client.getMutationCache().build(client, { mutationFn: async () => "datos anteriores" });
    await mutation.execute(undefined);
    replaceSession(client, user);
    expect(client.getQueryData(SESSION_KEY)).toEqual(user);
    expect(client.getQueryData(["driver-today"])).toBeUndefined();
    expect(client.getQueryData(["orders"])).toBeUndefined();
    expect(client.getMutationCache().getAll()).toHaveLength(0);
    expect(client.getQueryCache().getAll()).toHaveLength(1);
    client.clear();
  });

  it("una respuesta tardía de la cuenta anterior no repuebla la caché", async () => {
    const client = new QueryClient();
    let finish!: (data: string) => void;
    const pending = client.fetchQuery({ queryKey: ["driver-today"], queryFn: () => new Promise<string>((resolve) => { finish = resolve; }) }).catch(() => undefined);
    expect(client.isFetching()).toBe(1);
    replaceSession(client, nextUser);
    finish("Ruta privada anterior");
    await pending;
    expect(client.getQueryData(["driver-today"])).toBeUndefined();
    expect(client.getQueryData(SESSION_KEY)).toEqual(nextUser);
    expect(client.isFetching()).toBe(0);
    client.clear();
  });

  it("notifica al observador activo de sesión al expirar y al entrar con otra cuenta", () => {
    const client = new QueryClient();
    client.setQueryData(SESSION_KEY, { ...nextUser, id: 1 });
    const observer = new QueryObserver(client, { queryKey: SESSION_KEY, enabled: false });
    const received: unknown[] = [];
    const unsubscribe = observer.subscribe((result) => received.push(result.data));
    replaceSession(client, null);
    expect(observer.getCurrentResult().data).toBeNull();
    replaceSession(client, nextUser);
    expect(observer.getCurrentResult().data).toEqual(nextUser);
    expect(received).toContain(null);
    unsubscribe();
    client.clear();
  });
});
