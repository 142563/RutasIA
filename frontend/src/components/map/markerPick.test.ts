import { describe, expect, it, vi } from "vitest";
import { pickMarker } from "./markerPick";

describe("pickMarker", () => {
  it.each([undefined, "Enter", " "])("elige las coordenadas exactas con %s sin propagar otro clic", (key) => {
    const onPick = vi.fn();
    const event = { key, stopPropagation: vi.fn(), preventDefault: vi.fn() };
    pickMarker({ lat: 14.6, lng: -90.5 }, onPick, event);
    expect(onPick).toHaveBeenCalledExactlyOnceWith({ lat: 14.6, lng: -90.5 });
    expect(event.stopPropagation).toHaveBeenCalledOnce();
    expect(event.preventDefault).toHaveBeenCalledTimes(key === undefined ? 0 : 1);
  });
  it("conserva las teclas de navegación y el mapa sin selección", () => {
    const onPick = vi.fn();
    const event = { stopPropagation: vi.fn(), preventDefault: vi.fn() };
    pickMarker({ lat: 14.6, lng: -90.5 }, onPick, { ...event, key: "Tab" });
    pickMarker({ lat: 14.6, lng: -90.5 }, undefined, event);
    expect(onPick).not.toHaveBeenCalled();
    expect(event.stopPropagation).not.toHaveBeenCalled();
    expect(event.preventDefault).not.toHaveBeenCalled();
  });
});
