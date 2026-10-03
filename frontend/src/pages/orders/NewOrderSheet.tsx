import { CheckIcon } from "lucide-react";
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
import { PRIORITIES, useCreateOrder } from "@/lib/orders";
import { useNetwork } from "@/lib/queries";
import type { Priority } from "@/lib/types";

const EMPTY = { recipient: "", phone: "", address: "", reference: "", weight: "", packages: "1" };

export function NewOrderSheet({ onDone }: { onDone: () => void }) {
  const network = useNetwork();
  const create = useCreateOrder();
  const [form, setForm] = React.useState(EMPTY);
  const [priority, setPriority] = React.useState<Priority>("normal");
  const [location, setLocation] = React.useState<(LatLng & { label: string }) | null>(null);
  const [placeId, setPlaceId] = React.useState("");
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
          setPriority("normal");
          setSubmitted(false);
          onDone();
        },
      },
    );
  }

  return (
    <SheetContent title="Nuevo pedido" description="La entrega se asocia al nodo más cercano de la red vial.">
      <form onSubmit={submit} className="flex min-h-0 flex-1 flex-col" noValidate>
        <div className="flex flex-1 flex-col gap-4 overflow-y-auto px-6 py-5">
          <Field label="Destinatario" htmlFor="recipient" error={show("recipient")}>
            <Input id="recipient" value={form.recipient} onChange={set("recipient")} aria-invalid={!!show("recipient")} autoFocus />
          </Field>
          <Field label="Teléfono" htmlFor="phone">
            <Input id="phone" type="tel" inputMode="tel" value={form.phone} onChange={set("phone")} placeholder="5555-1234" />
          </Field>
          <Field label="Dirección de entrega" htmlFor="address" error={show("address")}>
            <AddressAutocomplete id="address" value={form.address} invalid={!!show("address")} placeholder="5a avenida 10-20, zona 1"
              onChange={(text) => { setForm((f) => ({ ...f, address: text })); setPlaceId(""); }}
              onPlace={(place) => {
                // Google dio dirección, coordenadas y place_id: se llena todo; el mapa y el municipio quedan como respaldo
                setForm((f) => ({ ...f, address: place.address }));
                setPlaceId(place.placeId);
                setLocation({ lat: place.lat, lng: place.lng, label: place.address });
              }} />
          </Field>
          <Field label="Ubicación" htmlFor="node-search" error={show("location")}
            hint="Se llena sola al elegir una dirección sugerida. Si no la encuentras, busca el municipio o haz clic en el mapa.">
            {network.data ? (
              <>
                <NodeSearch id="node-search" nodes={network.data.nodes}
                  onSelect={(node) => setLocation({ lat: node.lat, lng: node.lng, label: node.name })} />
                <div className="rounded-lg border border-line bg-bg">
                  <NetworkMap
                    nodes={network.data.nodes}
                    edges={network.data.edges}
                    width={400}
                    height={300}
                    labels="none"
                    onPick={(p) => setLocation({ ...p, label: `${p.lat.toFixed(4)}, ${p.lng.toFixed(4)}` })}
                    markers={location ? [{ id: "pick", kind: "pick", lat: location.lat, lng: location.lng }] : []}
                    ariaLabel="Haz clic para marcar el punto de entrega"
                  />
                </div>
                {location ? (
                  <p className="flex items-center gap-1.5 text-xs text-ok"><CheckIcon className="size-3.5" /> Ubicación elegida: {location.label}</p>
                ) : null}
              </>
            ) : (
              <p className="text-xs text-ink-2">Cargando la red vial…</p>
            )}
          </Field>
          <Field label="Referencias" htmlFor="reference">
            <Textarea id="reference" value={form.reference} onChange={set("reference")} placeholder="Portón negro, preguntar en recepción" />
          </Field>
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
        <div className="flex justify-end gap-2 border-t border-line px-6 py-4">
          <Button variant="outline" onClick={onDone}>Cancelar</Button>
          <Button type="submit" disabled={create.isPending}>{create.isPending ? "Guardando…" : "Guardar pedido"}</Button>
        </div>
      </form>
    </SheetContent>
  );
}
