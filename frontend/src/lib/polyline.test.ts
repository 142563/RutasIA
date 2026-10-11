import { describe, expect, it } from "vitest";
import { concatenateGeometry, decodePolyline } from "./polyline";

const encoded = "_p~iF~ps|U_ulLnnqC_mqNvxq`@";
describe("geometría dirigida", () => {
  it("decodifica coordenadas negativas y incrementos del ejemplo oficial", () => {
    expect(decodePolyline(encoded)).toEqual([
      { lat: 38.5, lng: -120.2 }, { lat: 40.7, lng: -120.95 }, { lat: 43.252, lng: -126.453 },
    ]);
  });
  it("conserva el orden elegido y elimina solo el extremo compartido", () => {
    expect(concatenateGeometry(["a", "b", "c"], [
      { from: "b", to: "c", polyline: "??AA" }, { from: "a", to: "b", polyline: "AAAA" },
    ])).toEqual([{ lat: 0.00001, lng: 0.00001 }, { lat: 0.00002, lng: 0.00002 }, { lat: 0, lng: 0 }, { lat: 0.00001, lng: 0.00001 }]);
    expect(concatenateGeometry(["a", "b", "c"], [
      { from: "a", to: "b", polyline: "??AA" }, { from: "b", to: "c", polyline: "AAAA" },
    ])).toHaveLength(3);
  });
  it("exige todas las aristas en su sentido exacto", () => {
    expect(concatenateGeometry(["b", "a"], [{ from: "a", to: "b", polyline: encoded }])).toBeNull();
    expect(concatenateGeometry(["a", "b", "c"], [{ from: "a", to: "b", polyline: encoded }])).toBeNull();
  });
  it("rechaza datos truncados, inválidos o de un solo punto para usar el respaldo", () => {
    for (const value of ["_", "!", "??", ""]) {
      expect(concatenateGeometry(["a", "b"], [{ from: "a", to: "b", polyline: value }])).toBeNull();
    }
    expect(() => decodePolyline("_")).toThrow();
  });
});
