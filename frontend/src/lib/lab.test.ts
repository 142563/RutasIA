import { describe, expect, it } from "vitest";
import { departureFor, isFinished, savingPct, totalSteps, visibleOrder } from "./lab";
import { bandFor, dayTypeFor } from "./traffic";

describe("animación del laboratorio", () => {
  const dijkstra = ["a", "b", "c", "d", "e", "f"];
  const astar = ["a", "c", "f"];

  it("ambas búsquedas avanzan al mismo ritmo y A* termina antes", () => {
    expect(visibleOrder(dijkstra, 2)).toEqual(["a", "b"]);
    expect(visibleOrder(astar, 2)).toEqual(["a", "c"]);
    expect(isFinished(astar, 3)).toBe(true);
    expect(isFinished(dijkstra, 3)).toBe(false);
    expect(totalSteps(dijkstra, astar)).toBe(6);
  });

  it("recorta pasos fuera de rango", () => {
    expect(visibleOrder(astar, -1)).toEqual([]);
    expect(visibleOrder(astar, 99)).toEqual(astar);
    expect(totalSteps()).toBe(0);
  });

  it("calcula el ahorro de nodos", () => {
    expect(savingPct(105, 36)).toBe(66);
    expect(savingPct(0, 0)).toBe(0);
  });
});

describe("departureFor", () => {
  const monday = new Date("2026-09-28T12:00:00-06:00");
  it("elige el próximo martes o sábado a la hora de la franja", () => {
    expect(departureFor("peak_am", "weekday", monday)).toBe("2026-09-29T08:00");
    expect(departureFor("night", "weekend", monday)).toBe("2026-10-03T23:00");
  });
  it("la salida cae en la franja y el tipo de día pedidos", () => {
    const iso = departureFor("peak_pm", "weekday", monday);
    const date = new Date(`${iso}:00-06:00`);
    expect(bandFor(date)).toBe("peak_pm");
    expect(dayTypeFor(date)).toBe("weekday");
  });
});
