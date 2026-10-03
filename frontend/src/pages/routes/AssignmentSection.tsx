import * as React from "react";
import { useNavigate } from "react-router";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Field, Select, Textarea } from "@/components/ui/field";
import { ErrorNote, Spinner } from "@/components/ui/misc";
import { Sheet, SheetContent } from "@/components/ui/sheet";
import {
  canManage, driverDisabled, driverNote, useAssignmentOptions, useAssignRoute, useCancelRoute, vehicleDisabled,
  vehicleNote,
} from "@/lib/assignment";
import type { RouteDetail } from "@/lib/dispatch";

type DetailRoute = RouteDetail["route"] & { driver_id?: number | null };

function Row({ label, value, hint }: { label: string; value: React.ReactNode; hint?: string }) {
  return (
    <div className="flex items-baseline justify-between gap-4 py-2.5 text-sm">
      <span className="text-ink-2">{label}</span>
      <span className="text-right">
        {value}
        {hint ? <span className="block text-xs text-ink-2">{hint}</span> : null}
      </span>
    </div>
  );
}

/** Panel lateral con selects que muestran quién está libre y qué camión alcanza. */
function ChangePanel({ route, open, onOpenChange }: { route: DetailRoute; open: boolean; onOpenChange: (open: boolean) => void }) {
  const options = useAssignmentOptions(route.id, open);
  const assign = useAssignRoute(route.id);
  const [driverId, setDriverId] = React.useState("");
  const [vehicleId, setVehicleId] = React.useState("");

  // Al abrir, se parte de lo que la ruta tiene hoy
  React.useEffect(() => {
    if (!open) return;
    setDriverId(route.driver_id ? String(route.driver_id) : "");
    const current = options.data?.vehicles.find((v) => v.plate === route.vehicle);
    setVehicleId(current ? String(current.id) : "");
  }, [open, route.driver_id, route.vehicle, options.data]);

  const data = options.data;
  const total = data?.total_weight_kg ?? null;

  function onVehicleChange(value: string) {
    setVehicleId(value);
    // Si el camión tiene piloto fijo y aún no hay piloto elegido, se sugiere
    const fixed = data?.vehicles.find((v) => String(v.id) === value)?.default_driver_id;
    const free = fixed != null && data?.drivers.some((d) => d.id === fixed && !d.busy);
    if (!driverId && free) setDriverId(String(fixed));
  }

  function save() {
    assign.mutate(
      { driver_id: driverId ? Number(driverId) : null, vehicle_id: vehicleId ? Number(vehicleId) : null },
      {
        onSuccess: () => {
          toast.success("Asignación actualizada.");
          onOpenChange(false);
        },
        onError: (error) => toast.error(error.message),
      },
    );
  }

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent title="Cambiar asignación" description={`${route.code}: elige quién la maneja y en qué camión.`}>
        <div className="flex flex-1 flex-col gap-5 overflow-y-auto px-6 py-5">
          {options.isPending ? <Spinner /> : null}
          {options.error ? <ErrorNote error={options.error} /> : null}
          {data ? (
            <>
              <Field label="Piloto" htmlFor="assign-driver" hint="Los pilotos ocupados en ese horario no se pueden elegir.">
                <Select id="assign-driver" value={driverId} onChange={(e) => setDriverId(e.target.value)}>
                  <option value="">Sin asignar</option>
                  {data.drivers.map((d) => {
                    const note = driverNote(d);
                    return (
                      <option key={d.id} value={d.id} disabled={driverDisabled(d)}>
                        {d.name}{note ? ` · ${note}` : ""}
                      </option>
                    );
                  })}
                </Select>
              </Field>
              <Field label="Camión" htmlFor="assign-vehicle"
                hint={total != null ? `Carga de esta ruta: ${Math.round(total).toLocaleString("es-GT")} kg.` : undefined}>
                <Select id="assign-vehicle" value={vehicleId} onChange={(e) => onVehicleChange(e.target.value)}>
                  <option value="">Sin asignar</option>
                  {data.vehicles.map((v) => {
                    const note = vehicleNote(v, total);
                    return (
                      <option key={v.id} value={v.id} disabled={vehicleDisabled(v)}>
                        {v.plate} · {v.model}{note ? ` · ${note}` : ""}
                      </option>
                    );
                  })}
                </Select>
              </Field>
            </>
          ) : null}
        </div>
        <div className="flex justify-end gap-2 border-t border-line px-6 py-4">
          <Button variant="outline" onClick={() => onOpenChange(false)}>Cerrar</Button>
          <Button onClick={save} disabled={!data || assign.isPending}>{assign.isPending ? "Guardando…" : "Guardar"}</Button>
        </div>
      </SheetContent>
    </Sheet>
  );
}

function CancelPanel({ route, open, onOpenChange }: { route: DetailRoute; open: boolean; onOpenChange: (open: boolean) => void }) {
  const navigate = useNavigate();
  const cancel = useCancelRoute(route.id);
  const [reason, setReason] = React.useState("");
  const pending = route.stops.length;

  function confirm() {
    cancel.mutate(reason.trim(), {
      onSuccess: (data) => {
        toast.success(`Ruta cancelada. ${data.released_orders} pedidos están pendientes otra vez.`);
        onOpenChange(false);
        navigate("/rutas");
      },
      onError: (error) => toast.error(error.message),
    });
  }

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent title="Cancelar ruta" description={`${route.code} dejará de estar en el plan.`}>
        <div className="flex flex-1 flex-col gap-4 overflow-y-auto px-6 py-5">
          <p className="text-sm text-ink-3">
            Los {pending} pedidos de esta ruta vuelven a Pendientes para que los puedas planificar de nuevo.
            La ruta se queda en el historial como cancelada.
          </p>
          <Field label="Motivo (opcional)" htmlFor="cancel-reason">
            <Textarea id="cancel-reason" value={reason} maxLength={120} onChange={(e) => setReason(e.target.value)}
              placeholder="Ej.: el cliente pidió cambiar la fecha" />
          </Field>
        </div>
        <div className="flex justify-end gap-2 border-t border-line px-6 py-4">
          <Button variant="outline" onClick={() => onOpenChange(false)}>Volver</Button>
          <Button variant="danger" onClick={confirm} disabled={cancel.isPending}>
            {cancel.isPending ? "Cancelando…" : "Sí, cancelar la ruta"}
          </Button>
        </div>
      </SheetContent>
    </Sheet>
  );
}

/** Bloque "Asignación" del detalle de ruta. */
export function AssignmentSection({ route }: { route: DetailRoute }) {
  const [changing, setChanging] = React.useState(false);
  const [canceling, setCanceling] = React.useState(false);
  const manageable = canManage(route);

  return (
    <section aria-label="Asignación">
      <h2 className="mb-1 text-sm font-semibold">Asignación</h2>
      <div className="divide-y divide-line border-y border-line">
        <Row label="Piloto" value={route.driver ?? <span className="font-medium text-warn">Sin asignar</span>} />
        <Row label="Camión" value={route.vehicle ?? <span className="text-ink-2">Sin asignar</span>} />
      </div>
      {manageable ? (
        <div className="mt-3 flex gap-2">
          <Button variant="outline" size="sm" onClick={() => setChanging(true)}>Cambiar</Button>
          <Button variant="danger" size="sm" onClick={() => setCanceling(true)}>Cancelar ruta</Button>
        </div>
      ) : (
        <p className="mt-3 text-xs text-ink-2">
          {route.status === "in_progress"
            ? "La ruta ya salió: no se puede reasignar ni cancelar desde aquí."
            : "Esta ruta ya no se puede cambiar."}
        </p>
      )}
      {manageable ? (
        <>
          <ChangePanel route={route} open={changing} onOpenChange={setChanging} />
          <CancelPanel route={route} open={canceling} onOpenChange={setCanceling} />
        </>
      ) : null}
    </section>
  );
}
