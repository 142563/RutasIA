import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "./api";
import type { Depot, Order, OrderStatus, Priority } from "./types";

export const STATUS: Record<OrderStatus, { label: string; color: string }> = {
  pending: { label: "Pendiente", color: "#a3a6ac" },
  assigned: { label: "Asignado", color: "#2f4bd8" },
  in_transit: { label: "En ruta", color: "#b45309" },
  delivered: { label: "Entregado", color: "#1a7f4b" },
  failed: { label: "No entregado", color: "#b42318" },
  canceled: { label: "Cancelado", color: "#6b6f76" },
};

export const PRIORITIES: { value: Priority; label: string }[] = [
  { value: "low", label: "Baja" },
  { value: "normal", label: "Normal" },
  { value: "high", label: "Alta" },
];

export interface OrdersResponse {
  orders: Order[];
  counts: Partial<Record<OrderStatus | "all", number>>;
}

export function useOrders(params: { status?: string; q?: string; ids?: string }) {
  return useQuery({
    queryKey: ["orders", params],
    queryFn: () => api<OrdersResponse>("/api/v2/orders/", { query: params }),
    placeholderData: (previous) => previous,
  });
}

export interface NewOrder {
  recipient: string;
  phone: string;
  address: string;
  reference: string;
  /** Id de Google Places si la dirección se eligió del autocompletado */
  place_id?: string;
  latitude: number;
  longitude: number;
  weight_kg: number;
  package_count: number;
  priority: Priority;
}

export function useCreateOrder() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (order: NewOrder) => api<{ order: Order }>("/api/v2/orders/", { method: "POST", body: order }),
    onSuccess: () => client.invalidateQueries({ queryKey: ["orders"] }),
  });
}

export function useDepots() {
  return useQuery({
    queryKey: ["depots"],
    queryFn: () => api<{ depots: Depot[] }>("/api/v2/depots/"),
    staleTime: 10 * 60 * 1000,
  });
}
