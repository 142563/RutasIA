import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";
import { TrafficRoads } from "./NetworkMap";
import type { LatLng } from "@/lib/geo";
import type { DrawnPair } from "@/lib/trafficMap";
import type { Pixel } from "@/lib/mapRendering";

const drawn: DrawnPair[] = [
  { pair: { key: "a>b", a: "a", b: "b", multiplier: 2, ab: 2, ba: 1 }, points: [{ lat: 0, lng: 0 }, { lat: 0, lng: 10 }] },
  { pair: { key: "c>d", a: "c", b: "d", multiplier: 1, ab: 1, ba: 1 }, points: [{ lat: 500, lng: 500 }, { lat: 500, lng: 510 }] },
];

describe("capa SVG de tráfico", () => {
  it("proyecta en coordenadas mundiales, traslada el grupo y omite carreteras fuera de pantalla", () => {
    const pixel = vi.fn((_point: LatLng): Pixel => [-9999, -9999]);
    const project = vi.fn((point: LatLng): Pixel => [point.lng, point.lat]);
    const toXY = Object.assign(pixel, { camera: { project, scale: 2, offset: [30, 40] as Pixel, viewport: [375, 200] as Pixel } });
    const html = renderToStaticMarkup(createElement(TrafficRoads, { drawn, toXY, nodes: [] }));
    expect(pixel).not.toHaveBeenCalled();
    expect(project).toHaveBeenCalledTimes(4);
    expect(html).toContain('transform="translate(30 40)"');
    expect(html).toContain('d="M0.00 0.00L20.00 0.00"');
    expect(html.match(/<path /g)).toHaveLength(1);
    expect(html).toContain("a → b: ×2 · b → a: ×1");
    expect(html).toContain('stroke-width="3"');
  });

  it("conserva el respaldo en píxeles cuando la proyección mundial aún no está disponible", () => {
    const toXY = (point: LatLng): Pixel => [point.lng + 7, point.lat + 9];
    const html = renderToStaticMarkup(createElement(TrafficRoads, { drawn: drawn.slice(0, 1), toXY, nodes: [] }));
    expect(html).toContain('d="M7.00 9.00L17.00 9.00"');
    expect(html).toContain('transform="translate(0 0)"');
  });
});
