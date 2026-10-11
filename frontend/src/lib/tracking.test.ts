import { describe, expect, it } from "vitest";
import { formatStepDate, formatWindow, isFinal, statusHint, statusTone, stepStates, visibleSteps, type TrackingData, type TrackingStep } from "./tracking";

const step = (key: TrackingStep["key"], done: boolean): TrackingStep => ({ key, label: key, at: null, done });

describe("stepStates", () => {
  it("marca el siguiente pendiente como actual", () => {
    const steps = [step("received", true), step("scheduled", true), step("on_the_way", false), step("delivered", false)];
    expect(stepStates(steps)).toEqual(["done", "done", "current", "todo"]);
  });
  it("todo hecho no deja pasos actuales", () => {
    expect(stepStates([step("received", true), step("delivered", true)])).toEqual(["done", "done"]);
  });
});

describe("visibleSteps", () => {
  it("oculta el paso de no entregado mientras no ocurre", () => {
    expect(visibleSteps([step("received", true), step("failed", false)]).map((s) => s.key)).toEqual(["received"]);
    expect(visibleSteps([step("received", true), step("failed", true)]).map((s) => s.key)).toEqual(["received", "failed"]);
  });
});

describe("fechas en hora de Guatemala", () => {
  it("formatea la ventana", () => {
    expect(formatWindow({ from: "2026-10-10T19:15:00Z", to: "2026-10-10T20:15:00Z" })).toBe("13:15 – 14:15");
    expect(formatWindow(null)).toBeNull();
  });
  it("formatea la fecha de un paso", () => {
    expect(formatStepDate("2026-10-10T20:32:00Z")).toContain("14:32");
    expect(formatStepDate(null)).toBe("");
  });
});

describe("estado", () => {
  const base: TrackingData = {
    code: "PED-1", status: "pending", status_label: "Pendiente", timeline: [], window: null,
    place: { municipality: null, region: null }, driver_name: null, note: null,
  };
  it("tonos", () => {
    expect(statusTone("delivered")).toBe("ok");
    expect(statusTone("failed")).toBe("err");
    expect(statusTone("in_transit")).toBe("accent");
    expect(statusTone("pending")).toBe("muted");
  });
  it("frases", () => {
    expect(statusHint({ ...base, status: "in_transit", driver_name: "Ana" })).toBe("Ana va en camino con tu pedido.");
    expect(statusHint({ ...base, status: "failed", note: "Te contactaremos." })).toBe("Te contactaremos.");
  });
  it("estados finales", () => {
    expect(isFinal("delivered")).toBe(true);
    expect(isFinal("assigned")).toBe(false);
  });
});
