import { describe, expect, it } from "vitest";
import { formatKm, formatMinutes } from "./format";
import { makeProjection } from "./geo";
import { bandFor, dayTypeFor } from "./traffic";

describe("formatMinutes", () => {
  it("usa horas y minutos con dos dígitos", () => {
    expect(formatMinutes(46)).toBe("46 min");
    expect(formatMinutes(64)).toBe("1 h 04 min");
    expect(formatMinutes(539.54)).toBe("9 h 00 min");
    expect(formatMinutes(null)).toBe("—");
  });
  it("formatea km", () => {
    expect(formatKm(437.75)).toBe("438 km");
    expect(formatKm(4.24)).toBe("4.2 km");
  });
});

describe("bandFor (hora de Guatemala, UTC−6)", () => {
  const at = (iso: string) => new Date(iso);
  it("respeta las fronteras de franja", () => {
    expect(bandFor(at("2026-10-06T06:59:00-06:00"))).toBe("dawn");
    expect(bandFor(at("2026-10-06T07:00:00-06:00"))).toBe("peak_am");
    expect(bandFor(at("2026-10-06T19:59:00-06:00"))).toBe("peak_pm");
    expect(bandFor(at("2026-10-06T20:00:00-06:00"))).toBe("night");
    expect(bandFor(at("2026-10-06T04:59:00-06:00"))).toBe("night");
  });
  it("convierte desde UTC", () => {
    expect(bandFor(at("2026-10-06T13:00:00Z"))).toBe("peak_am");
  });
  it("detecta el fin de semana en hora local", () => {
    expect(dayTypeFor(at("2026-10-03T10:00:00-06:00"))).toBe("weekend");
    // domingo 03:00 UTC = sábado 21:00 en Guatemala
    expect(dayTypeFor(at("2026-10-04T03:00:00Z"))).toBe("weekend");
    expect(dayTypeFor(at("2026-10-05T10:00:00-06:00"))).toBe("weekday");
  });
});

describe("makeProjection", () => {
  const pts = [
    { lat: 13.8, lng: -92.2 },
    { lat: 17.8, lng: -88.2 },
  ];
  const proj = makeProjection(pts, 800, 600, 20);
  it("el norte queda arriba y el oeste a la izquierda", () => {
    const [x1, y1] = proj.toXY(pts[0]);
    const [x2, y2] = proj.toXY(pts[1]);
    expect(x1).toBeLessThan(x2);
    expect(y1).toBeGreaterThan(y2);
  });
  it("queda dentro del lienzo y es invertible", () => {
    for (const p of pts) {
      const [x, y] = proj.toXY(p);
      expect(x).toBeGreaterThanOrEqual(20 - 1e-9);
      expect(x).toBeLessThanOrEqual(780 + 1e-9);
      expect(y).toBeGreaterThanOrEqual(20 - 1e-9);
      expect(y).toBeLessThanOrEqual(580 + 1e-9);
      const back = proj.toLatLng(x, y);
      expect(back.lat).toBeCloseTo(p.lat, 9);
      expect(back.lng).toBeCloseTo(p.lng, 9);
    }
  });
});
