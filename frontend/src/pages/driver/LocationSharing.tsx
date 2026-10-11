import * as React from "react";
import { Button } from "@/components/ui/button";
import { api } from "@/lib/api";
import { startLocationSharing } from "@/lib/locationShare";

export function LocationSharing({ routeId, active }: { routeId: number; active: boolean }) {
  const [enabled, setEnabled] = React.useState(false);
  const [message, setMessage] = React.useState("Ubicación sin compartir");
  React.useEffect(() => {
    if (!active) {
      setEnabled(false);
      return;
    }
    if (!enabled) return;
    if (!navigator.geolocation) {
      setMessage("Tu navegador no admite ubicación.");
      return;
    }
    return startLocationSharing(navigator.geolocation, (position, signal) =>
      api("/api/driver/position/", { method: "POST", body: { route_id: routeId, ...position }, signal }), setMessage);
  }, [routeId, active, enabled]);
  if (!active) return null;
  return (
    <section className="flex flex-col gap-2 rounded-xl border border-line bg-surface p-4" aria-label="Ubicación del vehículo">
      <p className="text-sm font-medium" role="status" aria-live="polite">{enabled ? message : "Ubicación sin compartir"}</p>
      <p className="text-[13px] text-ink-2">Si autorizas el GPS, el despachador verá tu ubicación durante esta ruta. Se detiene al salir de esta pantalla.</p>
      <Button variant="outline" className="min-h-12 whitespace-normal" onClick={() => {
        setMessage("Esperando permiso y ubicación…");
        setEnabled((value) => !value);
      }}>{enabled ? "Dejar de compartir" : "Autorizar y compartir ubicación"}</Button>
    </section>
  );
}
