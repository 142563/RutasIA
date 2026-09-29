import { describe, expect, it } from "vitest";
import { findStop, navigationUrl, nextStop, routeProgress, telUrl, type DriverStop, type DriverToday } from "./driver";

const stop = (id: number, sequence: number, status: DriverStop["status"]): DriverStop => ({
  id, sequence, order_code: `PED-${id}`, recipient: "X", phone: "", address: "", lat: 14.6, lng: -90.5, node: null,
  eta: "2026-09-28T08:00:00-06:00", status, status_label: "", reason: "", delivered_at: null,
});

describe("vista del conductor", () => {
  const route = { stops: [stop(3, 3, "pending"), stop(1, 1, "delivered"), stop(2, 2, "failed"), stop(4, 4, "pending")] };

  it("calcula el avance", () => {
    expect(routeProgress(route)).toEqual({ total: 4, delivered: 1, failed: 1, done: 2, percent: 50 });
    expect(routeProgress({ stops: [] }).percent).toBe(0);
  });

  it("elige la próxima parada pendiente por secuencia", () => {
    expect(nextStop(route)?.id).toBe(3);
    expect(nextStop({ stops: [stop(1, 1, "delivered")] })).toBeUndefined();
  });

  it("arma los enlaces de navegación y llamada", () => {
    expect(navigationUrl({ lat: 14.6, lng: -90.5 })).toBe("https://www.google.com/maps/dir/?api=1&destination=14.6,-90.5");
    expect(navigationUrl({ lat: null, lng: null })).toBeNull();
    expect(telUrl("5555-0001")).toBe("tel:55550001");
    expect(telUrl("")).toBeNull();
  });

  it("encuentra una parada en la ruta de hoy", () => {
    const data = { driver: { id: 1, name: "C", phone: "" }, date: "2026-09-28", routes: [{ ...route, id: 9 }] } as unknown as DriverToday;
    expect(findStop(data, 2)?.route.id).toBe(9);
    expect(findStop(data, 99)).toBeNull();
    expect(findStop(undefined, 1)).toBeNull();
  });
});
