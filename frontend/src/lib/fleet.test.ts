import { describe, expect, it } from "vitest";
import { parseLocation } from "./fleet";

describe("parseLocation", () => {
  it("lee coordenadas sueltas", () => {
    expect(parseLocation("14.6349, -90.5069")).toEqual({ lat: 14.6349, lng: -90.5069 });
    expect(parseLocation("14.6349 -90.5069")).toEqual({ lat: 14.6349, lng: -90.5069 });
  });
  it("lee enlaces de Google Maps", () => {
    expect(parseLocation("https://www.google.com/maps/place/Bodega/@14.6,-90.5,17z/data=x")).toEqual({ lat: 14.6, lng: -90.5 });
    expect(parseLocation("https://maps.google.com/?q=14.6,-90.5")).toEqual({ lat: 14.6, lng: -90.5 });
    expect(parseLocation("https://www.google.com/maps?q=14.6%2C-90.5")).toEqual({ lat: 14.6, lng: -90.5 });
    expect(parseLocation("https://x/data=!3d14.61!4d-90.52")).toEqual({ lat: 14.61, lng: -90.52 });
  });
  it("devuelve null si no hay coordenadas", () => {
    expect(parseLocation("zona 12")).toBeNull();
    expect(parseLocation("")).toBeNull();
  });
});
