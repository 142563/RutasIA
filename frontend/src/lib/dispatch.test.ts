import { describe, expect, it } from "vitest";
import { formatDiff, parseDataSource, progressOf, progressPct } from "./dispatch";

describe("progreso de ruta", () => {
  it("cuenta entregadas y fallidas como resueltas", () => {
    const p = progressOf([{ status: "delivered" }, { status: "failed" }, { status: "pending" }, { status: "pending" }]);
    expect(p).toEqual({ delivered: 1, failed: 1, total: 4 });
    expect(progressPct(p)).toBe(50);
    expect(progressPct({ delivered: 0, failed: 0, total: 0 })).toBe(0);
  });
});

describe("parseDataSource", () => {
  it("lee el formato de Route.data_source", () => {
    expect(parseDataSource("edges=estimate;traffic=synthetic")).toEqual({ edges: "estimate", traffic: "synthetic" });
    expect(parseDataSource("")).toBeUndefined();
  });
});

describe("formatDiff", () => {
  it("muestra el signo real − estimado", () => {
    expect(formatDiff(12.4)).toBe("+12 min");
    expect(formatDiff(-3)).toBe("−3 min");
    expect(formatDiff(0.2)).toBe("a la hora");
    expect(formatDiff(null)).toBe("—");
  });
});
