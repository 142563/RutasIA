import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "./api";

export type FleetKind = "depots" | "drivers" | "vehicles" | "users";
export type Role = "admin" | "dispatcher" | "driver";

export interface FleetDepot {
  id: number; name: string; address: string; latitude: number; longitude: number;
  node: { code: string; name: string } | null; is_active: boolean;
}
export interface FleetDriver {
  id: number; name: string; phone: string; license_number: string; is_active: boolean;
  user: { id: number; username: string } | null;
}
export interface FleetVehicle {
  id: number; plate: string; model: string; capacity_kg: number; fuel_efficiency_km_l: number;
  cost_per_km: number; driver: { id: number; name: string } | null; is_active: boolean;
}
export interface FleetUser {
  id: number; username: string; full_name: string; role: Role; role_label: string; is_active: boolean;
}

export interface FleetTypes {
  depots: FleetDepot; drivers: FleetDriver; vehicles: FleetVehicle; users: FleetUser;
}

export const ROLES: { value: Role; label: string }[] = [
  { value: "admin", label: "Administrador" },
  { value: "dispatcher", label: "Despachador" },
  { value: "driver", label: "Conductor" },
];

export function useFleet<K extends FleetKind>(kind: K) {
  return useQuery({
    queryKey: ["fleet", kind],
    queryFn: async () => (await api<Record<K, FleetTypes[K][]>>(`/api/v2/fleet/${kind}/`))[kind],
  });
}

/** Crea (sin id) o edita (con id) un registro; "desactivar/reactivar" es editar is_active. */
export function useSaveFleet(kind: FleetKind) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: ({ id, body }: { id?: number; body: Record<string, unknown> }) =>
      api<unknown>(id ? `/api/v2/fleet/${kind}/${id}/` : `/api/v2/fleet/${kind}/`, { method: id ? "PATCH" : "POST", body }),
    onSuccess: () => {
      // Los pilotos y usuarios se relacionan entre sí, y las bodegas/camiones alimentan el planificador.
      void client.invalidateQueries({ queryKey: ["fleet"] });
      void client.invalidateQueries({ queryKey: ["depots"] });
    },
  });
}

/**
 * Extrae latitud y longitud de lo que pegue el usuario: "14.63, -90.51", un enlace de Google Maps
 * con /@14.6,-90.5,15z, ?q=14.6,-90.5, !3d14.6!4d-90.5, o ll=14.6,-90.5. Devuelve null si no hay.
 */
export function parseLocation(text: string): { lat: number; lng: number } | null {
  const input = decodeURIComponent(text.trim().replace(/%(?![0-9a-f]{2})/gi, "%25"));
  const num = "(-?\\d{1,3}(?:\\.\\d+)?)";
  const patterns = [
    new RegExp(`!3d${num}!4d${num}`),
    new RegExp(`@${num},\\s*${num}`),
    new RegExp(`[?&](?:q|ll|query|destination)=${num}\\s*,\\s*${num}`),
    new RegExp(`^\\(?${num}\\s*[,; ]\\s*${num}\\)?$`),
  ];
  for (const pattern of patterns) {
    const m = input.match(pattern);
    if (m) {
      const lat = Number(m[1]);
      const lng = Number(m[2]);
      if (Math.abs(lat) <= 90 && Math.abs(lng) <= 180) return { lat, lng };
    }
  }
  return null;
}
