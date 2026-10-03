import { describe, expect, it } from "vitest";
import { formatLiveDiff, liveTone } from "./live";

describe("tráfico del momento", () => {
  it("formatea la diferencia", () => {
    expect(formatLiveDiff(25.4)).toBe("+25 min");
    expect(formatLiveDiff(-10)).toBe("−10 min");
    expect(formatLiveDiff(0.2)).toBe("sin cambio");
  });

  it("marca verde si coincide y ámbar si no", () => {
    expect(liveTone({ confirmed: true })).toBe("ok");
    expect(liveTone({ confirmed: false })).toBe("warn");
  });
});
