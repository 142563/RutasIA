import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { createDebouncer } from "./debounce";

describe("createDebouncer", () => {
  beforeEach(() => vi.useFakeTimers());
  afterEach(() => vi.useRealTimers());

  it("una ráfaga de cambios produce una sola solicitud (la última)", () => {
    const calls: number[] = [];
    const debouncer = createDebouncer(400);
    for (let i = 1; i <= 10; i++) {
      debouncer.run(() => calls.push(i));
      vi.advanceTimersByTime(100);
    }
    expect(calls).toEqual([]);
    vi.advanceTimersByTime(400);
    expect(calls).toEqual([10]);
  });

  it("cancelar evita la llamada pendiente", () => {
    const fn = vi.fn();
    const debouncer = createDebouncer(400);
    debouncer.run(fn);
    debouncer.cancel();
    vi.advanceTimersByTime(1000);
    expect(fn).not.toHaveBeenCalled();
  });
});
