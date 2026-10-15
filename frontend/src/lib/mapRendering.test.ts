import { describe, expect, it, vi } from "vitest";
import { frameScheduler, intersectsViewport, preparePixelPath, simplifyPixels, type Pixel } from "./mapRendering";

describe("geometría de dibujo del mapa", () => {
  it("reduce 20,545 puntos rectos a los extremos sin modificar la geometría original", () => {
    const original: Pixel[] = Array.from({ length: 20_545 }, (_, i) => [i / 100, i / 200]);
    const result = simplifyPixels(original);
    expect(result).toEqual([original[0], original.at(-1)]);
    expect(original).toHaveLength(20_545);
    expect(preparePixelPath(original, 1).d.match(/[ML]/g)).toHaveLength(2);
  });

  it("conserva las curvas y recupera detalle al acercar el mapa", () => {
    const points: Pixel[] = [[0, 0], [1, 0.5], [2, 0], [3, 4], [4, 0]];
    expect(simplifyPixels(points)).toEqual([[0, 0], [2, 0], [3, 4], [4, 0]]);
    expect(preparePixelPath(points, 4).d.match(/[ML]/g)).toHaveLength(5);
    expect(preparePixelPath(points, 1).bounds).toEqual({ left: 0, right: 4, top: 0, bottom: 4 });
  });

  it("maneja puntos vacíos, repetidos y tramos cortos sin NaN", () => {
    expect(preparePixelPath([], 1).d).toBe("");
    expect(simplifyPixels([[1, 1]])).toEqual([[1, 1]]);
    expect(simplifyPixels([[1, 1], [1, 1], [1, 1]])).toEqual([[1, 1], [1, 1]]);
    expect(preparePixelPath([[1, 2], [3, 4]], 2).d).toBe("M2.00 4.00L6.00 8.00");
  });

  it("omite tramos fuera de pantalla y conserva los que la cruzan sin extremos visibles", () => {
    const crossing = preparePixelPath([[-100, 50], [500, 50]], 1);
    expect(intersectsViewport(crossing.bounds, [0, 0], [375, 200])).toBe(true);
    expect(intersectsViewport(crossing.bounds, [0, 300], [375, 200])).toBe(false);
    expect(intersectsViewport(crossing.bounds, [0, -55], [375, 200])).toBe(true);
    expect(intersectsViewport(preparePixelPath([], 1).bounds, [0, 0], [375, 200])).toBe(false);
  });

  it("arrastra los mismos trazos sin alterar sus coordenadas ni volver a prepararlos", () => {
    const path = preparePixelPath([[0, 0], [1, 0], [2, 0]], 100);
    const before = path.d;
    expect(intersectsViewport(path.bounds, [20, 40], [375, 200])).toBe(true);
    expect(intersectsViewport(path.bounds, [400, 40], [375, 200])).toBe(false);
    expect(path.d).toBe(before);
  });
});

describe("avisos de cámara", () => {
  function fixture() {
    let callback: (() => void) | undefined;
    const draw = vi.fn();
    const request = vi.fn((fn: () => void) => { callback = fn; return 17; });
    const cancel = vi.fn();
    return { draw, request, cancel, flush: () => callback?.(), frames: frameScheduler(draw, request, cancel) };
  }

  it("agrupa draw y bounds_changed en un solo dibujo por cuadro y permite el siguiente", () => {
    const { frames, draw, request, flush } = fixture();
    for (let i = 0; i < 100; i++) frames.schedule();
    expect(request).toHaveBeenCalledTimes(1);
    expect(draw).not.toHaveBeenCalled();
    flush();
    expect(draw).toHaveBeenCalledTimes(1);
    frames.schedule();
    flush();
    expect(draw).toHaveBeenCalledTimes(2);
    expect(request).toHaveBeenCalledTimes(2);
  });

  it("cancela el cuadro pendiente y descarta avisos después de desmontar", () => {
    const { frames, draw, request, cancel, flush } = fixture();
    frames.schedule();
    frames.dispose();
    expect(cancel).toHaveBeenCalledExactlyOnceWith(17);
    flush();
    frames.schedule();
    expect(request).toHaveBeenCalledTimes(1);
    expect(draw).not.toHaveBeenCalled();
  });
});
