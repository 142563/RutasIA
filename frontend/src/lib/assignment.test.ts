import { describe, expect, it } from "vitest";
import { canManage, driverDisabled, driverNote, isUnassigned, vehicleDisabled, vehicleNote } from "./assignment";

const driver = { id: 1, name: "Ana", phone: "", has_mobile_account: true, busy: false, busy_route: null };
const vehicle = { id: 1, plate: "C-1", model: "Isuzu", capacity_kg: 2800, default_driver_id: null, default_driver: null,
  busy: false, busy_route: null, fits: true };

describe("assignment", () => {
  it("avisa cuando un piloto está ocupado o no tiene cuenta", () => {
    expect(driverNote(driver)).toBeNull();
    expect(driverNote({ ...driver, has_mobile_account: false })).toBe("Sin cuenta en el celular");
    const busy = { ...driver, busy: true, busy_route: { id: 2, code: "RUT-0002" } };
    expect(driverNote(busy)).toBe("Ocupado en RUT-0002");
    expect(driverDisabled(busy)).toBe(true);
    expect(driverDisabled({ ...driver, has_mobile_account: false })).toBe(false);
  });

  it("avisa cuando el camión no cabe", () => {
    const small = { ...vehicle, fits: false };
    expect(vehicleNote(small, 3200)).toMatch(/^No cabe: 3.?200 kg > 2.?800 kg$/);
    expect(vehicleDisabled(small)).toBe(true);
    expect(vehicleNote(vehicle, 1000)).toBeNull();
  });

  it("detecta rutas sin piloto y rutas gestionables", () => {
    expect(isUnassigned({ driver: null, status: "planned" })).toBe(true);
    expect(isUnassigned({ driver: null, status: "canceled" })).toBe(false);
    expect(isUnassigned({ driver: "Ana", status: "planned" })).toBe(false);
    expect(canManage({ status: "planned" })).toBe(true);
    expect(canManage({ status: "in_progress" })).toBe(false);
  });
});
