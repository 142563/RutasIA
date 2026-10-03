import { describe, expect, it } from "vitest";
import { parsePlace, parseSuggestions, shouldSearch } from "./places";

describe("autocompletado de direcciones", () => {
  it("solo busca con 3 letras o más", () => {
    expect(shouldSearch("  ab ")).toBe(false);
    expect(shouldSearch("5a av")).toBe(true);
  });

  it("parsea sugerencias y descarta las que no son lugares", () => {
    const out = parseSuggestions([
      { placePrediction: { placeId: "p1", text: { text: "5a Avenida 10-20, Guatemala" }, mainText: { text: "5a Avenida 10-20" }, secondaryText: { text: "Guatemala" } } },
      { placePrediction: null },
      { placePrediction: { text: { text: "sin id" } } },
    ]);
    expect(out).toEqual([{ placeId: "p1", main: "5a Avenida 10-20", secondary: "Guatemala", text: "5a Avenida 10-20, Guatemala" }]);
  });

  it("parsea el lugar elegido (location como LatLng de Google o literal)", () => {
    const fromGoogle = { id: "p1", formattedAddress: "5a Av 10-20, Guatemala", location: { lat: () => 14.6, lng: () => -90.5 } };
    expect(parsePlace(fromGoogle)).toEqual({ lat: 14.6, lng: -90.5, placeId: "p1", address: "5a Av 10-20, Guatemala" });
    expect(parsePlace({ location: { lat: 1, lng: 2 } }, "x", "texto")).toEqual({ lat: 1, lng: 2, placeId: "x", address: "texto" });
  });

  it("devuelve null si el lugar no trae coordenadas", () => {
    expect(parsePlace({ id: "p1", formattedAddress: "x" })).toBeNull();
  });
});
