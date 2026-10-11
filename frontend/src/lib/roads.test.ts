import { describe, expect, it } from "vitest";
import { distanceMeters, guideCodes, joinLegNodes, MAX_WAYPOINTS, needsConnector, routeConnectors, sampleWaypoints } from "./roads";

describe("submuestreo de waypoints", () => {
  const seq = (n: number) => Array.from({ length: n }, (_, i) => i);

  it("no toca las rutas cortas", () => {
    expect(sampleWaypoints(seq(10))).toEqual(seq(10));
    expect(sampleWaypoints(seq(MAX_WAYPOINTS + 2))).toHaveLength(MAX_WAYPOINTS + 2);
  });

  it("limita a 25 intermedios y conserva origen y destino en orden", () => {
    const out = sampleWaypoints(seq(120));
    expect(out).toHaveLength(MAX_WAYPOINTS + 2);
    expect(out[0]).toBe(0);
    expect(out[out.length - 1]).toBe(119);
    expect(out).toEqual([...out].sort((a, b) => a - b));
    expect(new Set(out).size).toBe(out.length);
  });

  it("reparte los puntos de forma pareja", () => {
    expect(sampleWaypoints(seq(101), 4)).toEqual([0, 20, 40, 60, 80, 100]);
  });
});

describe("puntos de guía para Directions", () => {
  const kinds: Record<string, string> = { A: "cabecera", B: "municipio", X: "cruce", C: "municipio", D: "cabecera", Y: "cruce" };
  const kindOf = (c: string) => kinds[c];

  it("descarta cabeceras y municipios intermedios; conserva extremos, paradas y cruces", () => {
    expect(guideCodes(["A", "B", "X", "C", "D"], [], kindOf)).toEqual(["A", "X", "D"]);
    expect(guideCodes(["A", "B", "X", "C", "D"], ["C"], kindOf)).toEqual(["A", "X", "C", "D"]);
  });

  it("sin paradas ni cruces solo quedan origen y destino", () => {
    expect(guideCodes(["A", "B", "C", "D"], [], kindOf)).toEqual(["A", "D"]);
  });
});

describe("tramos de conexión", () => {
  const node = { lat: 14.28, lng: -91.36 };
  it("distancia: ~111 km por grado de latitud", () => {
    expect(distanceMeters({ lat: 14, lng: -90 }, { lat: 15, lng: -90 })).toBeGreaterThan(110000);
    expect(distanceMeters({ lat: 14, lng: -90 }, { lat: 15, lng: -90 })).toBeLessThan(112000);
  });
  it("omite el tramo si el pedido ya está en el nodo o no tiene coordenadas", () => {
    expect(needsConnector(node, { lat: node.lat + 0.001, lng: node.lng })).toBe(false);
    const out = routeConnectors(null, null, [
      { id: 1, lat: node.lat + 0.001, lng: node.lng, node },
      { id: 2, lat: null, lng: null, node },
    ]);
    expect(out).toEqual([]);
  });
  it("crea bodega→nodo y nodo→pedido cuando difieren", () => {
    const depot = { lat: 14.63, lng: -90.51 };
    const depotNode = { lat: 14.6, lng: -90.5 };
    const out = routeConnectors(depot, depotNode, [{ id: 7, lat: 14.3, lng: -91.4, node }]);
    expect(out.map((c) => c.id)).toEqual(["depot", "stop-7"]);
    expect(out[1].from).toEqual(node);
    expect(out[1].to).toEqual({ lat: 14.3, lng: -91.4 });
  });
});

describe("unión de tramos", () => {
  it("no repite el nodo donde empalman los tramos", () => {
    expect(joinLegNodes([{ nodes: ["a", "b", "c"] }, { nodes: ["c", "d"] }, { nodes: ["d", "e"] }])).toEqual(["a", "b", "c", "d", "e"]);
  });
});
