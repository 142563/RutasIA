import { CornerDownLeftIcon, SearchIcon } from "lucide-react";
import { AnimatePresence, motion } from "motion/react";
import { Dialog } from "radix-ui";
import * as React from "react";
import { SPRING } from "@/components/ui/motion";
import { cn } from "@/lib/utils";

export interface Command {
  id: string;
  group: string;
  label: string;
  icon: React.ComponentType<{ className?: string }>;
  keywords?: string;
  run: () => void;
}

/** Quita tildes y pasa a minúsculas para buscar "trafico" y encontrar "Tráfico". */
export function normalize(text: string) {
  return text.normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase();
}

export function filterCommands(commands: Command[], query: string) {
  const q = normalize(query.trim());
  if (!q) return commands;
  return commands.filter((c) => normalize(`${c.label} ${c.keywords ?? ""} ${c.group}`).includes(q));
}

/** Búsqueda global (Ctrl/⌘K): ir a cualquier sección o ejecutar una acción con el teclado. */
export function CommandPalette({ open, onOpenChange, commands }: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  commands: Command[];
}) {
  const [query, setQuery] = React.useState("");
  const [index, setIndex] = React.useState(0);
  const results = filterCommands(commands, query);
  const listId = React.useId();

  React.useEffect(() => {
    if (open) {
      setQuery("");
      setIndex(0);
    }
  }, [open]);
  React.useEffect(() => setIndex(0), [query]);

  const run = (c: Command) => {
    onOpenChange(false);
    c.run();
  };

  const onKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setIndex((i) => Math.min(i + 1, results.length - 1));
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setIndex((i) => Math.max(i - 1, 0));
    } else if (e.key === "Enter" && results[index]) {
      e.preventDefault();
      run(results[index]);
    }
  };

  const groups = [...new Set(results.map((c) => c.group))];

  return (
    <Dialog.Root open={open} onOpenChange={onOpenChange}>
      <AnimatePresence>
        {open ? (
          <Dialog.Portal forceMount>
            <Dialog.Overlay asChild>
              <motion.div className="fixed inset-0 z-50 bg-black/30 backdrop-blur-[2px]"
                initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} transition={{ duration: 0.15 }} />
            </Dialog.Overlay>
            <Dialog.Content asChild aria-describedby={undefined}>
              <motion.div
                initial={{ opacity: 0, scale: 0.96, y: -8 }}
                animate={{ opacity: 1, scale: 1, y: 0 }}
                exit={{ opacity: 0, scale: 0.98, transition: { duration: 0.12 } }}
                transition={SPRING}
                className="fixed left-1/2 top-[14vh] z-50 w-[calc(100%-2rem)] max-w-lg -translate-x-1/2 overflow-hidden rounded-2xl border border-line bg-elevated shadow-pop"
                onKeyDown={onKeyDown}
              >
                <Dialog.Title className="sr-only">Buscar o ir a</Dialog.Title>
                <div className="flex items-center gap-3 border-b border-line px-4">
                  <SearchIcon className="size-4 shrink-0 text-ink-2" aria-hidden />
                  <input
                    autoFocus
                    value={query}
                    onChange={(e) => setQuery(e.target.value)}
                    placeholder="Escribe una sección o una acción…"
                    className="h-13 w-full bg-transparent text-[15px] outline-none placeholder:text-ink-2"
                    role="combobox"
                    aria-expanded
                    aria-controls={listId}
                    aria-activedescendant={results[index] ? `${listId}-${results[index].id}` : undefined}
                  />
                </div>
                <div id={listId} role="listbox" className="max-h-[50vh] overflow-y-auto p-2">
                  {results.length === 0 ? (
                    <p className="px-3 py-8 text-center text-[13px] text-ink-2">Nada coincide con “{query}”.</p>
                  ) : groups.map((g) => (
                    <div key={g} className="pb-1">
                      <p className="px-3 pb-1 pt-2 text-[11px] font-medium uppercase tracking-wide text-ink-2">{g}</p>
                      {results.filter((c) => c.group === g).map((c) => {
                        const i = results.indexOf(c);
                        const active = i === index;
                        const Icon = c.icon;
                        return (
                          <button
                            key={c.id}
                            id={`${listId}-${c.id}`}
                            type="button"
                            role="option"
                            aria-selected={active}
                            onMouseMove={() => setIndex(i)}
                            onClick={() => run(c)}
                            className={cn("relative flex h-10 w-full items-center gap-3 rounded-lg px-3 text-left text-sm", active ? "text-ink" : "text-ink-3")}
                          >
                            {active ? <motion.span layoutId="palette-active" transition={SPRING} className="absolute inset-0 rounded-lg bg-hover" aria-hidden /> : null}
                            <Icon className="relative size-4 text-ink-2" />
                            <span className="relative flex-1">{c.label}</span>
                            {active ? <CornerDownLeftIcon className="relative size-3.5 text-ink-2" aria-hidden /> : null}
                          </button>
                        );
                      })}
                    </div>
                  ))}
                </div>
                <div className="flex items-center gap-4 border-t border-line px-4 py-2 text-[11px] text-ink-2">
                  <span><kbd className="num">↑↓</kbd> moverse</span>
                  <span><kbd className="num">Enter</kbd> abrir</span>
                  <span><kbd className="num">Esc</kbd> cerrar</span>
                </div>
              </motion.div>
            </Dialog.Content>
          </Dialog.Portal>
        ) : null}
      </AnimatePresence>
    </Dialog.Root>
  );
}
