import { CheckIcon } from "lucide-react";
import { motion } from "motion/react";
import * as React from "react";
import { toast } from "sonner";
import { AddressAutocomplete } from "@/components/AddressAutocomplete";
import { NetworkMap } from "@/components/map/NetworkMap";
import { NodeSearch } from "@/components/NodeSearch";
import { Button } from "@/components/ui/button";
import { Field, Input, Textarea } from "@/components/ui/field";
import { Segmented } from "@/components/ui/misc";
import { SheetContent } from "@/components/ui/sheet";
import type { LatLng } from "@/lib/geo";
import { geocodeAddress, shouldGeocode, type LocationSource } from "@/lib/geocode";
import { useGoogleMaps } from "@/lib/googleMaps";
import { PRIORITIES, useCreateOrder } from "@/lib/orders";
import { useNetwork } from "@/lib/queries";
import type { Priority } from "@/lib/types";

const EMPTY = { recipient: "", phone: "", email: "", address: "", reference: "", weight: "", packages: "1" };

export function NewOrderSheet({ onDone }: { onDone: (createdCode?: string) => void }) {
  const network = useNetwork();
  const create = useCreateOrder();
  const [form, setForm] = React.useState(EMPTY);
  const [priority, setPriority] = React.useState<Priority>("normal");
  const [location, setLocation] = React.useState<(LatLng & { label: string }) | null>(null);
  const [placeId, setPlaceId] = React.useState("");
  // Cómo se fijó el punto y para qué texto: decide si al salir del campo se vuelve a geocodificar
  const [source, setSource] = React.useState<LocationSource | null>(null);
  // Punto al que se acerca el mapa (no cambia con cada clic del usuario sobre el mapa)
  const [focusPoint, setFocusPoint] = React.useState<LatLng | null>(null);
  const [geoState, setGeoState] = React.useState<"idle" | "searching" | "notfound">("idle");
  const google = useGoogleMaps();
  const latest = React.useRef({ address: "", source: null as LocationSource | null, locatedFor: "" });

  function placeAt(point: LatLng, label: string, how: LocationSource, text: string) {
    setLocation({ lat: point.lat, lng: point.lng, label });
    setSource(how);
    latest.current = { ...latest.current, source: how, locatedFor: text };
    if (how !== "map") setFocusPoint({ lat: point.lat, lng: point.lng });
  }

  async function geocodeTyped(text: string) {
    const now = latest.current;
    if (google.status !== "ready" || !shouldGeocode({ address: text, source: now.source, locatedFor: now.locatedFor })) return;
    setGeoState("searching");
    const found = await geocodeAddress(text.trim());
    // Si mientras tanto la persona cambió el texto o fijó el punto a mano, no se pisa
    const after = latest.current;
    if (after.address.trim() !== text.trim() || after.source === "node" || after.source === "map") { setGeoState("idle"); return; }
    if (!found) { setGeoState("notfound"); return; }
    setGeoState("idle");
    placeAt(found, found.address, "geocode", text);
  }
  const [submitted, setSubmitted] = React.useState(false);

  const set = (key: keyof typeof EMPTY) => (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) =>
    setForm((f) => ({ ...f, [key]: e.target.value }));

  const errors = {
    recipient: !form.recipient.trim() ? "Indica el destinatario." : null,
    address: !form.address.trim() ? "Indica la dirección de entrega." : null,
    location: !location ? "Elige el municipio o marca el punto en el mapa." : null,
    weight: !(Number(form.weight) > 0) ? "El peso debe ser mayor que 0." : null,
    packages: !(Number.isInteger(Number(form.packages)) && Number(form.packages) >= 1) ? "Al menos 1 bulto." : null,
  };
  const valid = Object.values(errors).every((e) => e === null);
  const show = (key: keyof typeof errors) => (submitted ? errors[key] : null);

  function submit(event: React.FormEvent) {
    event.preventDefault();
    setSubmitted(true);
    if (!valid || !location) return;
    create.mutate(
      {
        recipient: form.recipient.trim(),
        phone: form.phone.trim(),
        recipient_email: form.email.trim(),
        address: form.address.trim(),
        reference: form.reference.trim(),
        place_id: placeId || undefined,
        latitude: location.lat,
        longitude: location.lng,
        weight_kg: Number(form.weight),
        package_count: Number(form.packages),
        priority,
      },
      {
        onSuccess: ({ order }) => {
          toast.success(`Pedido ${order.code} guardado`, { description: `Asociado al nodo ${order.node?.name ?? "—"}` });
          setForm(EMPTY);
          setLocation(null);
          setPlaceId("");
          setSource(null);
          setFocusPoint(null);
          setGeoState("idle");
          latest.current = { address: "", source: null, locatedFor: "" };
          setPriority("normal");
          setSubmitted(false);
          onDone(order.code);
        },
      },
    );
  }

  return (
    <SheetContent title="Nuevo pedido" description="La entrega se asocia al nodo más cercano de la red vial.">
      <form onSubmit={submit} className="flex min-h-0 flex-1 flex-col" noValidate>
        <div className="flex flex-1 flex-col gap-5 overflow-y-auto px-6 py-5">
          <h3 className="text-xs font-medium uppercase tracking-wide text-ink-2">Destinatario</h3>
          <Field label="Destinatario" htmlFor="recipient" error={show("recipient")}>
            <Input id="recipient" value={form.recipient} onChange={set("recipient")} aria-invalid={!!show("recipient")} autoFocus />
          </Field>
          <Field label="Teléfono" htmlFor="phone">
            <Input id="phone" type="tel" inputMode="tel" value={form.phone} onChange={set("phone")} placeholder="5555-1234" />
          </Field>
          <Field label="Correo del cliente (opcional)" htmlFor="email" hint="Le avisaremos cuando su pedido sea entregado.">
            <Input id="email" type="email" inputMode="email" value={form.email} onChange={set("email")} placeholder="cliente@correo.com" />
          </Field>
          <div className="h-px bg-line" />
          <h3 className="text-xs font-medium uppercase tracking-wide text-ink-2">Entrega</h3>
          <Field label="Dirección de entrega" htmlFor="address" error={show("address")}>
            <AddressAutocomplete id="address" value={form.address} invalid={!!show("address")} placeholder="5a avenida 10-20, zona 1"
              onChange={(text) => {
                latest.current = { ...latest.current, address: text };
                setForm((f) => ({ ...f, address: text }));
                setPlaceId("");
                setGeoState("idle");
              }}
              onSettle={(text) => void geocodeTyped(text)}
              onPlace={(place) => {
                // Google dio dirección, coordenadas y place_id: se llena todo; el mapa y el municipio quedan como respaldo
                latest.current = { ...latest.current, address: place.address };
                setForm((f) => ({ ...f, address: place.address }));
                setPlaceId(place.placeId);
                placeAt(place, place.address, "place", place.address);
              }} />
          </Field>
          <Field label="Ubicación" htmlFor="node-search" error={show("location")}
            hint="Se llena sola al escribir la dirección. Si no se ubica bien, busca el municipio o haz clic en el mapa.">
            {network.data ? (
              <>
                <NodeSearch id="node-search" nodes={network.data.nodes}
                  onSelect={(node) => placeAt({ lat: node.lat, lng: node.lng }, node.name, "node", form.address)} />
                <div className="rounded-lg border border-line bg-bg">
                  <NetworkMap
                    nodes={network.data.nodes}
                    edges={network.data.edges}
                    width={400}
                    height={300}
                    labels="none"
                    fitTo={focusPoint && google.status === "ready" ? [focusPoint] : undefined}
                    onPick={(p) => placeAt(p, `${p.lat.toFixed(4)}, ${p.lng.toFixed(4)}`, "map", form.address)}
                    markers={location ? [{ id: "pick", kind: "pick", lat: location.lat, lng: location.lng }] : []}
                    ariaLabel="Haz clic para marcar el punto de entrega"
                  />
                </div>
                {geoState === "searching" ? <p className="text-xs text-ink-2" role="status">Buscando la dirección…</p> : null}
                {geoState === "notfound" ? <p className="text-xs text-ink-2" role="status">No pudimos ubicar esa dirección. Elige el municipio o haz clic en el mapa.</p> : null}
                {google.status === "unavailable" ? <p className="text-xs text-ink-2" role="status">Google Maps no está disponible, así que la dirección no se ubica sola. Elige el municipio o haz clic en el mapa.</p> : null}
                {location ? (
                  <motion.p initial={{ opacity: 0, y: -4 }} animate={{ opacity: 1, y: 0 }} className="flex items-start gap-1.5 text-xs text-ok"><CheckIcon className="mt-0.5 size-3.5 shrink-0" />
                    <span>{source === "map" || source === "node" ? "Ubicación elegida" : "Ubicado"}: {location.label}
                      {source === "place" || source === "geocode" ? <span className="text-ink-2"> · ¿No es aquí? Haz clic en el mapa para corregir.</span> : null}</span>
                  </motion.p>
                ) : null}
              </>
            ) : (
              <p className="text-xs text-ink-2">Cargando la red vial…</p>
            )}
          </Field>
          <Field label="Referencias" htmlFor="reference">
            <Textarea id="reference" value={form.reference} onChange={set("reference")} placeholder="Portón negro, preguntar en recepción" />
          </Field>
          <div className="h-px bg-line" />
          <h3 className="text-xs font-medium uppercase tracking-wide text-ink-2">Paquete</h3>
          <div className="grid grid-cols-2 gap-3">
            <Field label="Peso (kg)" htmlFor="weight" error={show("weight")}>
              <Input id="weight" type="number" min="0" step="0.1" inputMode="decimal" className="num" value={form.weight} onChange={set("weight")} aria-invalid={!!show("weight")} />
            </Field>
            <Field label="Bultos" htmlFor="packages" error={show("packages")}>
              <Input id="packages" type="number" min="1" step="1" inputMode="numeric" className="num" value={form.packages} onChange={set("packages")} aria-invalid={!!show("packages")} />
            </Field>
          </div>
          <div className="flex flex-col gap-1.5">
            <span className="text-[13px] font-medium text-ink-3">Prioridad</span>
            <Segmented label="Prioridad" value={priority} onChange={setPriority} options={PRIORITIES} />
          </div>
          {create.error ? <p className="text-[13px] text-err" role="alert">{create.error.message}</p> : null}
        </div>
        <div className="flex justify-end gap-2 border-t border-line bg-elevated px-6 py-4">
          <Button variant="outline" onClick={() => onDone()}>Cancelar</Button>
          <Button type="submit" disabled={create.isPending}>{create.isPending ? "Guardando…" : "Guardar pedido"}</Button>
        </div>
      </form>
    </SheetContent>
  );
}
