import { describe, expect, it } from "vitest";
import { parseGeocode, shouldGeocode } from "./geocode";

describe("cuándo geocodificar al salir del campo", () => {
  it("geocodifica una dirección escrita sin ubicación previa", () => {
    expect(shouldGeocode({ address: "3a calle 4-5, Tiquisate", source: null, locatedFor: "" })).toBe(true);
  });
  it("no geocodifica textos muy cortos", () => {
    expect(shouldGeocode({ address: "ab", source: null, locatedFor: "" })).toBe(false);
  });
  it("respeta un punto fijado a mano (municipio o mapa)", () => {
    expect(shouldGeocode({ address: "3a calle 4-5, Tiquisate", source: "map", locatedFor: "" })).toBe(false);
    expect(shouldGeocode({ address: "3a calle 4-5, Tiquisate", source: "node", locatedFor: "" })).toBe(false);
  });
  it("no repite si el texto no cambió desde que se ubicó", () => {
    expect(shouldGeocode({ address: "Calle X ", source: "place", locatedFor: "Calle X" })).toBe(false);
    expect(shouldGeocode({ address: "Calle X", source: "geocode", locatedFor: "Calle X" })).toBe(false);
  });
  it("vuelve a buscar si se editó la dirección ubicada antes", () => {
    expect(shouldGeocode({ address: "Calle Y, Tiquisate", source: "geocode", locatedFor: "Calle X" })).toBe(true);
    expect(shouldGeocode({ address: "Calle Y, Tiquisate", source: "place", locatedFor: "Calle X" })).toBe(true);
  });
});

describe("resultado del geocodificador", () => {
  it("toma el primer resultado con coordenadas (números o funciones)", () => {
    const out = parseGeocode([
      { formatted_address: "sin coordenadas" },
      { formatted_address: "Tiquisate, Escuintla, Guatemala", geometry: { location: { lat: () => 14.28, lng: () => -91.36 } } },
    ]);
    expect(out).toEqual({ lat: 14.28, lng: -91.36, address: "Tiquisate, Escuintla, Guatemala" });
    expect(parseGeocode([{ geometry: { location: { lat: 1, lng: 2 } } }], "mi texto")).toEqual({ lat: 1, lng: 2, address: "mi texto" });
  });
  it("devuelve null sin resultados o con coordenadas inválidas", () => {
    expect(parseGeocode([])).toBeNull();
    expect(parseGeocode(null)).toBeNull();
    expect(parseGeocode([{ geometry: { location: { lat: NaN, lng: 1 } } }])).toBeNull();
  });
});
