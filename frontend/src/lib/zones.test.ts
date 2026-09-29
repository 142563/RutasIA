import { describe, expect, it } from "vitest";
import type { Order } from "./types";
import { groupByZone, placesLabel } from "./zones";

function order(id: number, region: [string, string] | null, place: string, weight = 1): Order {
  return {
    id, code: `P${id}`, recipient: "x", phone: "", address: "", reference: "", latitude: 0, longitude: 0,
    node: { code: place.toLowerCase(), name: place }, region: region ? { code: region[0], name: region[1] } : null,
    weight_kg: weight, package_count: 1, priority: "normal", status: "pending", status_label: "Pendiente",
    is_demo: true, created_at: "",
  };
}

describe("groupByZone", () => {
  it("agrupa por región y ordena por cantidad de pedidos", () => {
    const zones = groupByZone([
      order(1, ["VI", "Suroccidente"], "Quetzaltenango", 2),
      order(2, ["I", "Metropolitana"], "Mixco"),
      order(3, ["VI", "Suroccidente"], "Retalhuleu", 3),
      order(4, ["VI", "Suroccidente"], "Quetzaltenango"),
    ]);
    expect(zones.map((z) => z.name)).toEqual(["Suroccidente", "Metropolitana"]);
    expect(zones[0].orderIds).toEqual([1, 3, 4]);
    expect(zones[0].weightKg).toBe(6);
    expect(zones[0].places).toEqual(["Quetzaltenango", "Retalhuleu"]);
  });

  it("junta los pedidos sin región", () => {
    expect(groupByZone([order(1, null, "X")])[0].name).toBe("Sin región");
  });
});

describe("placesLabel", () => {
  it("resume listas largas", () => {
    expect(placesLabel(["A", "B"])).toBe("A, B");
    expect(placesLabel(["A", "B", "C", "D", "E"])).toBe("A, B, C y 2 más");
  });
});
