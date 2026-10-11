import { describe, expect, it } from "vitest";
import type { RouteStopRow } from "./dispatch";
import { routeSheetStops } from "./routeSheet";

describe("routeSheetStops", () => {
  const stops = [
    { id: 20, sequence: 2, order_code: "PED-2" },
    { id: 10, sequence: 1, order_code: "PED-1" },
  ] as RouteStopRow[];

  it("ordena por visita y asocia la referencia por código sin modificar la ruta", () => {
    const rows = routeSheetStops(stops, [
      { code: "PED-2", reference: "Portón azul" },
      { code: "PED-1", reference: "Frente al parque" },
      { code: "PED-3", reference: "Otro pedido" },
    ]);
    expect(rows.map((row) => [row.id, row.reference])).toEqual([[10, "Frente al parque"], [20, "Portón azul"]]);
    expect(stops.map((stop) => stop.id)).toEqual([20, 10]);
    expect(stops[0]).not.toHaveProperty("reference");
  });

  it("distingue una referencia vacía de un pedido que falta", () => {
    const rows = routeSheetStops(stops, [{ code: "PED-1", reference: "" }]);
    expect(rows[0].reference).toBe("");
    expect(rows[1].reference).toBeNull();
  });
});
