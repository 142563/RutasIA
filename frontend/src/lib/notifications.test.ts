import { describe, expect, it } from "vitest";
import { NOTIFICATION_STATUS, notificationLine, notificationWhen } from "./notifications";

describe("avisos enviados", () => {
  it("arma la línea con evento, audiencia y correo enmascarado", () => {
    expect(notificationLine({ event_label: "Pedido entregado", audience_label: "Cliente", recipient: "j***@gmail.com" }))
      .toBe("Pedido entregado · Cliente · j***@gmail.com");
  });

  it("cada estado tiene texto y color de token", () => {
    expect(NOTIFICATION_STATUS.sent.label).toBe("Enviado");
    expect(NOTIFICATION_STATUS.failed.label).toBe("Falló");
    expect(NOTIFICATION_STATUS.skipped.label).toBe("Sin enviar");
    for (const s of Object.values(NOTIFICATION_STATUS)) expect(s.color).toMatch(/^var\(--color-/);
  });

  it("la fecha usa la hora de Guatemala y tolera fechas inválidas", () => {
    expect(notificationWhen("2026-10-11T20:32:00Z")).toContain("14:32");
    expect(notificationWhen("no es fecha")).toBe("");
  });
});
