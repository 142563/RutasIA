import { MapPinIcon } from "lucide-react";
import * as React from "react";
import { Input } from "@/components/ui/field";
import type { GraphNode } from "@/lib/types";
import { cn } from "@/lib/utils";

const KIND_LABEL = { cabecera: "Cabecera", municipio: "Municipio", cruce: "Cruce", "": "" } as const;

function normalize(text: string) {
  return text.normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase();
}

/** Buscador de municipios/cruces del grafo (sin acentos, por nombre). */
export function NodeSearch({ nodes, onSelect, id, placeholder = "Buscar municipio…" }: {
  nodes: GraphNode[];
  onSelect: (node: GraphNode) => void;
  id?: string;
  placeholder?: string;
}) {
  const [text, setText] = React.useState("");
  const [open, setOpen] = React.useState(false);
  const [active, setActive] = React.useState(0);
  const listId = React.useId();

  const matches = React.useMemo(() => {
    const q = normalize(text.trim());
    if (!q) return [];
    return nodes
      .filter((n) => normalize(n.name).includes(q))
      .sort((a, b) => Number(normalize(b.name).startsWith(q)) - Number(normalize(a.name).startsWith(q)))
      .slice(0, 8);
  }, [nodes, text]);

  function choose(node: GraphNode) {
    onSelect(node);
    setText(node.name);
    setOpen(false);
  }

  return (
    <div className="relative">
      <Input
        id={id}
        role="combobox"
        aria-expanded={open && matches.length > 0}
        aria-controls={listId}
        aria-autocomplete="list"
        placeholder={placeholder}
        value={text}
        onChange={(e) => {
          setText(e.target.value);
          setOpen(true);
          setActive(0);
        }}
        onBlur={() => setTimeout(() => setOpen(false), 120)}
        onKeyDown={(e) => {
          if (!matches.length) return;
          if (e.key === "ArrowDown") { e.preventDefault(); setActive((i) => Math.min(i + 1, matches.length - 1)); }
          if (e.key === "ArrowUp") { e.preventDefault(); setActive((i) => Math.max(i - 1, 0)); }
          if (e.key === "Enter") { e.preventDefault(); choose(matches[active]); }
          if (e.key === "Escape") setOpen(false);
        }}
      />
      {open && matches.length > 0 ? (
        <ul id={listId} role="listbox" className="absolute inset-x-0 top-full z-10 mt-1 max-h-64 overflow-auto rounded-lg border border-line bg-surface py-1 shadow-sm">
          {matches.map((node, i) => (
            <li
              key={node.code}
              role="option"
              aria-selected={i === active}
              onMouseDown={(e) => { e.preventDefault(); choose(node); }}
              onMouseEnter={() => setActive(i)}
              className={cn("flex cursor-pointer items-center gap-2 px-3 py-2 text-sm", i === active && "bg-hover")}
            >
              <MapPinIcon className="size-3.5 text-ink-2" aria-hidden />
              <span className="flex-1">{node.name}</span>
              <span className="text-xs text-ink-2">{KIND_LABEL[node.kind]}</span>
            </li>
          ))}
        </ul>
      ) : null}
    </div>
  );
}
