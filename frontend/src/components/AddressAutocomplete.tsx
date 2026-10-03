import * as React from "react";
import { Input } from "@/components/ui/field";
import { useGoogleMaps } from "@/lib/googleMaps";
import { fetchPlace, fetchSuggestions, newSessionToken, useDebounced, type ChosenPlace, type PlaceSuggestion } from "@/lib/places";
import { cn } from "@/lib/utils";

/**
 Campo de dirección con sugerencias de Google Places (New) limitadas a Guatemala.

 Sin Google (sin key, key rechazada o sin red) es un campo de texto normal: la entrada manual
 sigue funcionando igual. Al elegir una sugerencia se entrega la dirección formateada, lat/lng
 y place_id. Una sesión de Places (token) agrupa las teclas y la elección para no gastar de más.
*/
export function AddressAutocomplete({ id, value, onChange, onPlace, invalid, placeholder }: {
  id?: string;
  value: string;
  /** Texto escrito a mano (también se llama al elegir una sugerencia, con la dirección formateada). */
  onChange: (text: string) => void;
  onPlace: (place: ChosenPlace) => void;
  invalid?: boolean;
  placeholder?: string;
}) {
  const google = useGoogleMaps();
  const enabled = google.status === "ready";
  const [typed, setTyped] = React.useState(""); // solo lo que escribe la persona, no lo elegido
  const debounced = useDebounced(typed, 300);
  const [suggestions, setSuggestions] = React.useState<PlaceSuggestion[]>([]);
  const [open, setOpen] = React.useState(false);
  const [active, setActive] = React.useState(0);
  const token = React.useRef<google.maps.places.AutocompleteSessionToken | null>(null);
  const listId = React.useId();

  React.useEffect(() => {
    if (!enabled) return;
    let alive = true;
    (async () => {
      if (!token.current) token.current = await newSessionToken();
      const found = await fetchSuggestions(debounced, token.current);
      if (alive) { setSuggestions(found); setActive(0); }
    })();
    return () => { alive = false; };
  }, [debounced, enabled]);

  async function choose(suggestion: PlaceSuggestion) {
    setOpen(false);
    setSuggestions([]);
    setTyped("");
    onChange(suggestion.text);
    const place = await fetchPlace(suggestion);
    token.current = null; // la sesión termina al elegir; la siguiente búsqueda abre otra
    if (place) {
      onChange(place.address);
      onPlace(place);
    }
  }

  const showList = enabled && open && suggestions.length > 0;
  return (
    <div className="relative">
      <Input
        id={id}
        value={value}
        placeholder={placeholder}
        aria-invalid={invalid}
        autoComplete="off"
        role={enabled ? "combobox" : undefined}
        aria-expanded={enabled ? showList : undefined}
        aria-controls={enabled ? listId : undefined}
        aria-autocomplete={enabled ? "list" : undefined}
        onChange={(e) => {
          onChange(e.target.value);
          setTyped(e.target.value);
          setOpen(true);
        }}
        onFocus={() => setOpen(true)}
        onBlur={() => setTimeout(() => setOpen(false), 150)}
        onKeyDown={(e) => {
          if (!showList) return;
          if (e.key === "ArrowDown") { e.preventDefault(); setActive((i) => Math.min(i + 1, suggestions.length - 1)); }
          if (e.key === "ArrowUp") { e.preventDefault(); setActive((i) => Math.max(i - 1, 0)); }
          if (e.key === "Enter") { e.preventDefault(); void choose(suggestions[active]); }
          if (e.key === "Escape") setOpen(false);
        }}
      />
      {showList ? (
        <ul id={listId} role="listbox"
          className="absolute z-20 mt-1 max-h-64 w-full overflow-auto rounded-lg border border-line bg-surface py-1 shadow-lg">
          {suggestions.map((s, i) => (
            <li key={s.placeId} role="option" aria-selected={i === active}
              onMouseDown={(e) => { e.preventDefault(); void choose(s); }}
              onMouseEnter={() => setActive(i)}
              className={cn("cursor-pointer px-3 py-2 text-sm", i === active && "bg-bg")}>
              <span className="block truncate text-ink">{s.main}</span>
              {s.secondary ? <span className="block truncate text-xs text-ink-2">{s.secondary}</span> : null}
            </li>
          ))}
        </ul>
      ) : null}
    </div>
  );
}
