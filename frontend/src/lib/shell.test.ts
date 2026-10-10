import { describe, expect, it } from "vitest";
import { filterCommands, normalize, type Command } from "@/components/layout/CommandPalette";
import { resolveTheme } from "@/lib/theme";

const noop = () => {};
const icon = () => null;
const commands: Command[] = [
  { id: "a", group: "Ir a", label: "Tráfico por hora", icon, run: noop },
  { id: "b", group: "Ir a", label: "Pedidos", icon, run: noop },
  { id: "c", group: "Acciones", label: "Cerrar sesión", icon, keywords: "salir", run: noop },
];

describe("búsqueda global", () => {
  it("ignora tildes y mayúsculas", () => {
    expect(normalize("TRÁFICO")).toBe("trafico");
    expect(filterCommands(commands, "trafico").map((c) => c.id)).toEqual(["a"]);
  });
  it("busca también en palabras clave", () => {
    expect(filterCommands(commands, "salir").map((c) => c.id)).toEqual(["c"]);
  });
  it("sin texto devuelve todo", () => {
    expect(filterCommands(commands, "  ")).toHaveLength(3);
  });
});

describe("tema", () => {
  it("'system' sigue al sistema; claro/oscuro lo fuerzan", () => {
    expect(resolveTheme("system", true)).toBe("dark");
    expect(resolveTheme("system", false)).toBe("light");
    expect(resolveTheme("light", true)).toBe("light");
    expect(resolveTheme("dark", false)).toBe("dark");
  });
});
