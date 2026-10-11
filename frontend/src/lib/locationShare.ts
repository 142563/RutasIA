export interface PhonePosition {
  lat: number; lng: number; speed_kmh: number | null; heading: number | null; accuracy_m: number | null;
}

const SEND_INTERVAL = 12_000;
const MAX_FIX_AGE = 30_000;

/** Empieza solo después del botón de permiso; la función devuelta revoca el seguimiento. */
export function startLocationSharing(
  geo: Pick<Geolocation, "watchPosition" | "clearWatch">,
  send: (position: PhonePosition, signal: AbortSignal) => Promise<unknown>,
  report: (message: string) => void,
) {
  let alive = true;
  let latest: GeolocationPosition | null = null;
  let busy = false;
  let watcher: number | undefined;
  let timer: ReturnType<typeof setInterval> | undefined;
  const abort = new AbortController();
  function stop() {
    alive = false;
    if (watcher !== undefined) geo.clearWatch(watcher);
    clearInterval(timer);
    abort.abort();
  }
  async function transmit() {
    if (!alive || busy) return;
    if (!latest || Date.now() - latest.timestamp > MAX_FIX_AGE) {
      report("Esperando una ubicación reciente…");
      return;
    }
    const coords = latest.coords;
    busy = true;
    try {
      await send({ lat: coords.latitude, lng: coords.longitude,
        speed_kmh: coords.speed == null ? null : coords.speed * 3.6,
        heading: coords.heading != null && Number.isFinite(coords.heading) ? coords.heading : null,
        accuracy_m: coords.accuracy }, abort.signal);
      if (alive) report("Compartiendo ubicación");
    } catch (error) {
      if (!alive) return;
      const status = (error as { status?: number }).status;
      if (status && [400, 401, 403, 404].includes(status)) stop();
      report(status && [400, 401, 403, 404].includes(status)
        ? "Ubicación detenida. Revisa si tu ruta sigue en curso."
        : "No se pudo enviar tu ubicación. Se reintentará mientras compartas.");
    } finally {
      busy = false;
    }
  }
  try {
    report("Esperando permiso y ubicación…");
    watcher = geo.watchPosition((position) => {
      if (alive) latest = position;
    }, (error) => {
      if (!alive) return;
      if (error.code === 1) {
        stop();
        report("No autorizaste la ubicación. Puedes habilitarla en tu navegador.");
      } else report("No se pudo obtener tu ubicación. Revisa el GPS de tu celular.");
    }, { enableHighAccuracy: true, maximumAge: 5000, timeout: 15000 });
    if (!alive) {
      geo.clearWatch(watcher);
      return stop;
    }
    timer = setInterval(() => { void transmit(); }, SEND_INTERVAL);
  } catch {
    stop();
    report("No se pudo activar la ubicación en este navegador.");
  }
  return stop;
}
