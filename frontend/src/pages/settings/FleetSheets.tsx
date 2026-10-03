import * as React from "react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Field, Input, Select } from "@/components/ui/field";
import { SheetContent } from "@/components/ui/sheet";
import {
  parseLocation, ROLES, useFleet, useSaveFleet,
  type FleetDepot, type FleetDriver, type FleetKind, type FleetUser, type FleetVehicle, type Role,
} from "@/lib/fleet";

interface ShellProps {
  kind: FleetKind;
  id?: number;
  title: string;
  description?: string;
  isActive?: boolean;
  /** Devuelve el cuerpo a enviar o null si hay errores de validación. */
  build: () => Record<string, unknown> | null;
  onSubmitAttempt: () => void;
  noun: string;
  onDone: () => void;
  children: React.ReactNode;
}

/** Panel lateral común: formulario, guardar y desactivar/reactivar. */
function FormShell({ kind, id, title, description, isActive, build, onSubmitAttempt, noun, onDone, children }: ShellProps) {
  const save = useSaveFleet(kind);

  function submit(event: React.FormEvent) {
    event.preventDefault();
    onSubmitAttempt();
    const body = build();
    if (!body) return;
    save.mutate({ id, body }, {
      onSuccess: () => { toast.success(id ? "Cambios guardados" : `Se agregó ${noun}`); onDone(); },
    });
  }

  function toggleActive() {
    save.mutate({ id, body: { is_active: !isActive } }, {
      onSuccess: () => { toast.success(isActive ? "Desactivado: ya no aparecerá al planificar" : "Activado de nuevo"); onDone(); },
    });
  }

  return (
    <SheetContent title={title} description={description}>
      <form onSubmit={submit} className="flex min-h-0 flex-1 flex-col" noValidate>
        <div className="flex flex-1 flex-col gap-4 overflow-y-auto px-6 py-5">
          {children}
          {save.error ? <p className="text-[13px] text-err" role="alert">{save.error.message}</p> : null}
        </div>
        <div className="flex items-center justify-between gap-2 border-t border-line px-6 py-4">
          {id ? (
            <Button variant={isActive ? "danger" : "outline"} onClick={toggleActive} disabled={save.isPending}>
              {isActive ? "Desactivar" : "Reactivar"}
            </Button>
          ) : <span />}
          <div className="flex gap-2">
            <Button variant="outline" onClick={onDone}>Cancelar</Button>
            <Button type="submit" disabled={save.isPending}>{save.isPending ? "Guardando…" : "Guardar"}</Button>
          </div>
        </div>
      </form>
    </SheetContent>
  );
}

const set = <T,>(setter: React.Dispatch<React.SetStateAction<T>>, key: keyof T) =>
  (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) => setter((f) => ({ ...f, [key]: e.target.value }));

// --- bodega ------------------------------------------------------------------

export function DepotSheet({ item, onDone }: { item: FleetDepot | null; onDone: () => void }) {
  const [form, setForm] = React.useState({
    name: item?.name ?? "", address: item?.address ?? "",
    place: item ? `${item.latitude}, ${item.longitude}` : "",
  });
  const [submitted, setSubmitted] = React.useState(false);
  const location = parseLocation(form.place);
  const errors = {
    name: form.name.trim() ? null : "Ponle un nombre a la bodega.",
    place: location ? null : "Pega las coordenadas (14.6349, -90.5069) o un enlace de Google Maps.",
  };

  return (
    <FormShell kind="depots" id={item?.id} isActive={item?.is_active} noun="la bodega" onDone={onDone}
      title={item ? "Editar bodega" : "Nueva bodega"} description="Desde aquí salen tus camiones."
      onSubmitAttempt={() => setSubmitted(true)}
      build={() => (errors.name || errors.place || !location ? null
        : { name: form.name.trim(), address: form.address.trim(), latitude: location.lat, longitude: location.lng })}>
      <Field label="Nombre" htmlFor="depot-name" error={submitted ? errors.name : null}>
        <Input id="depot-name" value={form.name} onChange={set(setForm, "name")} placeholder="Bodega zona 12" autoFocus aria-invalid={submitted && !!errors.name} />
      </Field>
      <Field label="Dirección" htmlFor="depot-address">
        <Input id="depot-address" value={form.address} onChange={set(setForm, "address")} placeholder="Calzada Aguilar Batres 10-20, zona 12" />
      </Field>
      <Field label="Ubicación" htmlFor="depot-place" error={submitted ? errors.place : null}
        hint="En Google Maps, haz clic derecho sobre la bodega, copia las coordenadas y pégalas aquí. También sirve copiar el enlace.">
        <Input id="depot-place" value={form.place} onChange={set(setForm, "place")} placeholder="14.6349, -90.5069" aria-invalid={submitted && !!errors.place} />
      </Field>
      {location ? (
        <p className="num text-xs text-ok">Ubicación leída: {location.lat.toFixed(5)}, {location.lng.toFixed(5)}</p>
      ) : null}
    </FormShell>
  );
}

// --- piloto ------------------------------------------------------------------

export function DriverSheet({ item, onDone }: { item: FleetDriver | null; onDone: () => void }) {
  const users = useFleet("users");
  const drivers = useFleet("drivers");
  const [form, setForm] = React.useState({ name: item?.name ?? "", phone: item?.phone ?? "", license: item?.license_number ?? "" });
  const [account, setAccount] = React.useState<"none" | "new" | "existing">(item?.user ? "existing" : "none");
  const [creds, setCreds] = React.useState({ username: "", password: "" });
  const [userId, setUserId] = React.useState(item?.user ? String(item.user.id) : "");
  const [submitted, setSubmitted] = React.useState(false);

  // Cuentas de conductor que aún no tienen piloto (más la de este piloto).
  const taken = new Set((drivers.data ?? []).filter((d) => d.id !== item?.id && d.user).map((d) => d.user!.id));
  const available = (users.data ?? []).filter((u) => u.role === "driver" && u.is_active && !taken.has(u.id));
  const hasCreds = account !== "new" || (creds.username.trim() && creds.password.length >= 10);
  const errors = {
    name: form.name.trim() ? null : "Indica el nombre del piloto.",
    license: form.license.trim() ? null : "Indica el número de licencia.",
    account: account === "new" && !hasCreds ? "Usuario y una contraseña de al menos 10 caracteres." : null,
  };

  function build() {
    if (errors.name || errors.license || errors.account) return null;
    const body: Record<string, unknown> = { name: form.name.trim(), phone: form.phone.trim(), license_number: form.license.trim() };
    if (account === "new") Object.assign(body, { username: creds.username.trim(), password: creds.password });
    else if (account === "existing") body.user_id = userId ? Number(userId) : null;
    else if (item) body.user_id = null;
    return body;
  }

  return (
    <FormShell kind="drivers" id={item?.id} isActive={item?.is_active} noun="al piloto" onDone={onDone}
      title={item ? "Editar piloto" : "Nuevo piloto"} description="Quien maneja los camiones y recibe sus rutas en el celular."
      onSubmitAttempt={() => setSubmitted(true)} build={build}>
      <Field label="Nombre" htmlFor="driver-name" error={submitted ? errors.name : null}>
        <Input id="driver-name" value={form.name} onChange={set(setForm, "name")} autoFocus aria-invalid={submitted && !!errors.name} />
      </Field>
      <div className="grid grid-cols-2 gap-3">
        <Field label="Teléfono" htmlFor="driver-phone">
          <Input id="driver-phone" type="tel" inputMode="tel" value={form.phone} onChange={set(setForm, "phone")} placeholder="5555-1234" />
        </Field>
        <Field label="Licencia" htmlFor="driver-license" error={submitted ? errors.license : null}>
          <Input id="driver-license" className="num" value={form.license} onChange={set(setForm, "license")} aria-invalid={submitted && !!errors.license} />
        </Field>
      </div>
      <Field label="Cuenta para el celular" htmlFor="driver-account" hint="Con ella el piloto entra a ver y completar sus rutas.">
        <Select id="driver-account" value={account} onChange={(e) => setAccount(e.target.value as typeof account)}>
          <option value="none">Sin cuenta</option>
          <option value="new">Crear una cuenta nueva</option>
          <option value="existing">Usar una cuenta existente</option>
        </Select>
      </Field>
      {account === "new" ? (
        <>
          <Field label="Usuario" htmlFor="driver-username">
            <Input id="driver-username" value={creds.username} onChange={set(setCreds, "username")} autoComplete="off" />
          </Field>
          <Field label="Contraseña" htmlFor="driver-password" error={submitted ? errors.account : null} hint="Mínimo 10 caracteres.">
            <Input id="driver-password" type="password" value={creds.password} onChange={set(setCreds, "password")} autoComplete="new-password" />
          </Field>
        </>
      ) : null}
      {account === "existing" ? (
        <Field label="Cuenta" htmlFor="driver-user" hint={available.length === 0 && !item?.user ? "No hay cuentas de conductor libres. Crea una nueva." : undefined}>
          <Select id="driver-user" value={userId} onChange={(e) => setUserId(e.target.value)}>
            <option value="">Sin cuenta</option>
            {item?.user ? <option value={item.user.id}>{item.user.username}</option> : null}
            {available.filter((u) => u.id !== item?.user?.id).map((u) => <option key={u.id} value={u.id}>{u.username}</option>)}
          </Select>
        </Field>
      ) : null}
    </FormShell>
  );
}

// --- camión ------------------------------------------------------------------

export function VehicleSheet({ item, onDone }: { item: FleetVehicle | null; onDone: () => void }) {
  const drivers = useFleet("drivers");
  const [form, setForm] = React.useState({
    plate: item?.plate ?? "", model: item?.model ?? "", capacity: item ? String(item.capacity_kg) : "",
    efficiency: item ? String(item.fuel_efficiency_km_l) : "", cost: item ? String(item.cost_per_km) : "",
    driver: item?.driver ? String(item.driver.id) : "",
  });
  const [submitted, setSubmitted] = React.useState(false);
  const errors = {
    plate: form.plate.trim() ? null : "Indica la placa.",
    capacity: Number(form.capacity) > 0 ? null : "La capacidad debe ser mayor que 0.",
    efficiency: !form.efficiency || Number(form.efficiency) > 0 ? null : "Debe ser mayor que 0.",
    cost: !form.cost || Number(form.cost) > 0 ? null : "Debe ser mayor que 0.",
  };
  const options = (drivers.data ?? []).filter((d) => d.is_active || String(d.id) === form.driver);

  function build() {
    if (Object.values(errors).some(Boolean)) return null;
    const body: Record<string, unknown> = {
      plate: form.plate.trim(), model: form.model.trim(), capacity_kg: Number(form.capacity),
      driver_id: form.driver ? Number(form.driver) : null,
    };
    // Si se dejan vacíos al crear, el servidor usa valores razonables.
    if (form.efficiency) body.fuel_efficiency_km_l = Number(form.efficiency);
    if (form.cost) body.cost_per_km = Number(form.cost);
    return body;
  }

  return (
    <FormShell kind="vehicles" id={item?.id} isActive={item?.is_active} noun="el camión" onDone={onDone}
      title={item ? "Editar camión" : "Nuevo camión"} description="Su capacidad se usa al planificar las rutas."
      onSubmitAttempt={() => setSubmitted(true)} build={build}>
      <div className="grid grid-cols-2 gap-3">
        <Field label="Placa" htmlFor="v-plate" error={submitted ? errors.plate : null}>
          <Input id="v-plate" className="num uppercase" value={form.plate} onChange={set(setForm, "plate")} placeholder="C-123ABC" autoFocus aria-invalid={submitted && !!errors.plate} />
        </Field>
        <Field label="Modelo" htmlFor="v-model">
          <Input id="v-model" value={form.model} onChange={set(setForm, "model")} placeholder="Hino 300" />
        </Field>
      </div>
      <Field label="Capacidad (kg)" htmlFor="v-capacity" error={submitted ? errors.capacity : null}>
        <Input id="v-capacity" type="number" min="0" step="1" inputMode="decimal" className="num" value={form.capacity} onChange={set(setForm, "capacity")} aria-invalid={submitted && !!errors.capacity} />
      </Field>
      <div className="grid grid-cols-2 gap-3">
        <Field label="Rendimiento (km por litro)" htmlFor="v-eff" error={submitted ? errors.efficiency : null} hint="Opcional. Si lo dejas vacío usamos 8.">
          <Input id="v-eff" type="number" min="0" step="0.1" inputMode="decimal" className="num" value={form.efficiency} onChange={set(setForm, "efficiency")} />
        </Field>
        <Field label="Costo por km (Q)" htmlFor="v-cost" error={submitted ? errors.cost : null} hint="Opcional. Si lo dejas vacío usamos Q2.50.">
          <Input id="v-cost" type="number" min="0" step="0.1" inputMode="decimal" className="num" value={form.cost} onChange={set(setForm, "cost")} />
        </Field>
      </div>
      <Field label="Piloto fijo" htmlFor="v-driver" hint="Opcional. Se sugiere al asignar rutas con este camión.">
        <Select id="v-driver" value={form.driver} onChange={set(setForm, "driver")}>
          <option value="">Sin piloto fijo</option>
          {options.map((d) => <option key={d.id} value={d.id}>{d.name}</option>)}
        </Select>
      </Field>
    </FormShell>
  );
}

// --- usuario -----------------------------------------------------------------

export function UserSheet({ item, onDone }: { item: FleetUser | null; onDone: () => void }) {
  const [form, setForm] = React.useState({ username: item?.username ?? "", full_name: item?.full_name ?? "", password: "" });
  const [role, setRole] = React.useState<Role>(item?.role ?? "dispatcher");
  const [submitted, setSubmitted] = React.useState(false);
  const errors = {
    username: form.username.trim() ? null : "Indica el nombre de usuario.",
    password: (!item || form.password) && form.password.length < 10 ? "La contraseña debe tener al menos 10 caracteres." : null,
  };

  function build() {
    if (errors.username || errors.password) return null;
    const body: Record<string, unknown> = { username: form.username.trim(), full_name: form.full_name.trim(), role };
    if (form.password) body.password = form.password;
    return body;
  }

  return (
    <FormShell kind="users" id={item?.id} isActive={item?.is_active} noun="al usuario" onDone={onDone}
      title={item ? "Editar usuario" : "Nuevo usuario"} description="Quién puede entrar al sistema y qué puede hacer."
      onSubmitAttempt={() => setSubmitted(true)} build={build}>
      <Field label="Usuario" htmlFor="u-username" error={submitted ? errors.username : null}>
        <Input id="u-username" value={form.username} onChange={set(setForm, "username")} autoComplete="off" autoFocus aria-invalid={submitted && !!errors.username} />
      </Field>
      <Field label="Nombre completo" htmlFor="u-name">
        <Input id="u-name" value={form.full_name} onChange={set(setForm, "full_name")} />
      </Field>
      <Field label="Rol" htmlFor="u-role" hint="Administrador: todo. Despachador: pedidos y rutas. Conductor: solo su ruta en el celular.">
        <Select id="u-role" value={role} onChange={(e) => setRole(e.target.value as Role)}>
          {ROLES.map((r) => <option key={r.value} value={r.value}>{r.label}</option>)}
        </Select>
      </Field>
      <Field label={item ? "Nueva contraseña" : "Contraseña"} htmlFor="u-password" error={submitted ? errors.password : null}
        hint={item ? "Déjala vacía para no cambiarla." : "Mínimo 10 caracteres."}>
        <Input id="u-password" type="password" value={form.password} onChange={set(setForm, "password")} autoComplete="new-password" />
      </Field>
    </FormShell>
  );
}
