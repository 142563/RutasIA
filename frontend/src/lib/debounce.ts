import * as React from "react";

/**
 Programa `fn` para dentro de `ms`; cada nueva llamada cancela la anterior.
 Así una ráfaga de cambios (marcar varios pedidos, escribir la hora) termina en una sola solicitud.
*/
export function createDebouncer(ms: number, timers: Pick<typeof globalThis, "setTimeout" | "clearTimeout"> = globalThis) {
  let handle: ReturnType<typeof setTimeout> | undefined;
  return {
    run(fn: () => void) {
      if (handle !== undefined) timers.clearTimeout(handle);
      handle = timers.setTimeout(() => {
        handle = undefined;
        fn();
      }, ms);
    },
    cancel() {
      if (handle !== undefined) timers.clearTimeout(handle);
      handle = undefined;
    },
  };
}

/** Devuelve `value` solo cuando deja de cambiar durante `ms` (compara por contenido, no por referencia). */
export function useDebouncedValue<T>(value: T, ms: number): T {
  const key = JSON.stringify(value);
  const [settled, setSettled] = React.useState(value);
  const debouncer = React.useMemo(() => createDebouncer(ms), [ms]);
  React.useEffect(() => {
    debouncer.run(() => setSettled(value));
    return () => debouncer.cancel();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key, debouncer]);
  return settled;
}
