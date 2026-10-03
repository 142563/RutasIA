import { describe, expect, it } from "vitest";
import { incidentHeadline, placesLabel, roadsLabel, savingLabel, timeAgo, type Incident } from "./incidents";

const edge = (road: string, a: string, b: string) => ({
  id: 1, road, km: 5, from: { code: a, name: a }, to: { code: b, name: b },
});
const incident = (edges: Incident["edges"]): Incident => ({
  id: 1, kind: "traffic", kind_label: "Tránsito pesado", blocked: false, starts_at: "", ends_at: null,
  note: "", route_id: null, reported_by: null, edges,
});

describe("incidentes", () => {
  it("resume el tramo por sus lugares", () => {
    expect(placesLabel([edge("CA-9", "Escuintla", "Palín"), edge("CA-9", "Palín", "Amatitlán")])).toBe("Escuintla → Amatitlán");
    expect(placesLabel([])).toBe("Tramo sin identificar");
  });
  it("junta carreteras sin repetir", () => {
    expect(roadsLabel([edge("CA-9", "a", "b"), edge("CA-9", "b", "c"), edge("CA-1", "c", "d")])).toBe("CA-9, CA-1");
  });
  it("arma el título del aviso", () => {
    expect(incidentHeadline(incident([edge("CA-9 Sur", "a", "b")]))).toBe("Tránsito pesado en CA-9 Sur");
    expect(incidentHeadline(incident([edge("", "Escuintla", "Palín")]))).toBe("Tránsito pesado en Escuintla → Palín");
    expect(incidentHeadline(undefined)).toBe("Hay un problema en tu camino");
  });
  it("formatea el ahorro", () => {
    expect(savingLabel({ minutes_saved: 18.4, current_blocked: false })).toBe("−18 min");
    expect(savingLabel({ minutes_saved: 0, current_blocked: true })).toBe("evita el tramo cerrado");
  });
  it("dice hace cuánto", () => {
    const now = new Date("2026-10-02T12:00:00Z");
    expect(timeAgo("2026-10-02T11:55:00Z", now)).toBe("hace 5 min");
    expect(timeAgo("2026-10-02T09:00:00Z", now)).toBe("hace 3 h");
    expect(timeAgo("2026-10-02T12:00:00Z", now)).toBe("hace un momento");
  });
});
