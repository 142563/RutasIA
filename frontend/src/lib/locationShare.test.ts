import { afterEach, describe, expect, it, vi } from "vitest";
import { startLocationSharing } from "./locationShare";

function setup() {
  let success: PositionCallback = () => {};
  let failure: PositionErrorCallback = () => {};
  const geo = {
    watchPosition: vi.fn((yes: PositionCallback, no?: PositionErrorCallback | null) => {
      success = yes;
      failure = no ?? (() => {});
      return 7;
    }), clearWatch: vi.fn(),
  };
  const report = vi.fn();
  const send = vi.fn(async () => ({}));
  const fix = () => success({ timestamp: Date.now(), coords: { latitude: 14.6, longitude: -90.5,
    accuracy: 8, speed: 10, heading: 90 } } as GeolocationPosition);
  return { geo, report, send, fix, failure: (code: number) => failure({ code } as GeolocationPositionError) };
}

afterEach(() => vi.useRealTimers());
describe("seguimiento voluntario", () => {
  it("solo envía desde el inicio explícito y cada 12 segundos", async () => {
    vi.useFakeTimers();
    const s = setup();
    expect(s.geo.watchPosition).not.toHaveBeenCalled();
    const stop = startLocationSharing(s.geo, s.send, s.report);
    s.fix();
    await vi.advanceTimersByTimeAsync(11_999);
    expect(s.send).not.toHaveBeenCalled();
    await vi.advanceTimersByTimeAsync(1);
    expect(s.send).toHaveBeenCalledWith({ lat: 14.6, lng: -90.5, speed_kmh: 36, heading: 90, accuracy_m: 8 }, expect.any(AbortSignal));
    expect(s.report).toHaveBeenLastCalledWith("Compartiendo ubicación");
    stop();
    expect(s.geo.clearWatch).toHaveBeenCalledWith(7);
    await vi.advanceTimersByTimeAsync(24_000);
    expect(s.send).toHaveBeenCalledTimes(1);
  });
  it("no transmite mediciones viejas ni después de revocar permiso", async () => {
    vi.useFakeTimers();
    const s = setup();
    const stop = startLocationSharing(s.geo, s.send, s.report);
    await vi.advanceTimersByTimeAsync(36_000);
    expect(s.send).not.toHaveBeenCalled();
    s.fix();
    s.failure(1);
    await vi.advanceTimersByTimeAsync(12_000);
    expect(s.send).not.toHaveBeenCalled();
    expect(s.geo.clearWatch).toHaveBeenCalledWith(7);
    stop();
  });
  it("no solapa envíos y cancela una petición pendiente al salir", async () => {
    vi.useFakeTimers();
    const s = setup();
    let signal: AbortSignal | undefined;
    const send = vi.fn((_value, received: AbortSignal) => {
      signal = received;
      return new Promise(() => {});
    });
    const stop = startLocationSharing(s.geo, send, s.report);
    s.fix();
    await vi.advanceTimersByTimeAsync(12_000);
    await vi.advanceTimersByTimeAsync(24_000);
    expect(send).toHaveBeenCalledTimes(1);
    stop();
    expect(signal?.aborted).toBe(true);
  });
  it("deja de enviar cuando la última medición envejece", async () => {
    vi.useFakeTimers();
    const s = setup();
    const stop = startLocationSharing(s.geo, s.send, s.report);
    s.fix();
    await vi.advanceTimersByTimeAsync(36_000);
    expect(s.send).toHaveBeenCalledTimes(2);
    expect(s.report).toHaveBeenLastCalledWith("Esperando una ubicación reciente…");
    stop();
  });
  it("detiene el watcher cuando el servidor rechaza la ruta", async () => {
    vi.useFakeTimers();
    const s = setup();
    const send = vi.fn(async () => { throw { status: 400 }; });
    const stop = startLocationSharing(s.geo, send, s.report);
    s.fix();
    await vi.advanceTimersByTimeAsync(12_000);
    expect(s.geo.clearWatch).toHaveBeenCalledWith(7);
    await vi.advanceTimersByTimeAsync(12_000);
    expect(send).toHaveBeenCalledTimes(1);
    stop();
  });
});
