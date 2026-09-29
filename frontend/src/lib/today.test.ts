import { describe, expect, it } from "vitest";
import { nextStep, type TodayState } from "./today";

const base: TodayState = { pendingOrders: 0, routesInProgress: 0, routesPlannedToday: 0, delayedStops: 0, pendingReroutes: 0 };

describe("nextStep", () => {
  it("sin nada: registrar el primer pedido", () => {
    expect(nextStep(base).cta?.to).toBe("/pedidos");
  });

  it("con pedidos pendientes: planificar", () => {
    const step = nextStep({ ...base, pendingOrders: 16, routesInProgress: 1 });
    expect(step.title).toBe("Tienes 16 pedidos sin ruta");
    expect(step.cta?.to).toBe("/planificar");
  });

  it("los retrasos van antes que los pendientes", () => {
    expect(nextStep({ ...base, pendingOrders: 3, delayedStops: 1 }).title).toBe("1 entrega va con retraso");
  });

  it("un recálculo por decidir es lo más urgente", () => {
    expect(nextStep({ ...base, pendingOrders: 3, delayedStops: 2, pendingReroutes: 1 }).tone).toBe("warn");
    expect(nextStep({ ...base, pendingReroutes: 1 }).cta?.to).toBe("/rutas");
  });

  it("todo asignado: en orden", () => {
    expect(nextStep({ ...base, routesInProgress: 2 }).tone).toBe("ok");
  });
});
