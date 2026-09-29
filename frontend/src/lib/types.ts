/** Tipos de las respuestas de la API (logistics/application/routing.py y app_views.py). */
import type { Band, DayType } from "./traffic";

export type Role = "admin" | "dispatcher" | "driver";

export interface User {
  id: number;
  username: string;
  full_name: string;
  role: Role;
  role_label: string;
  driver_id: number | null;
}

export interface DataSource {
  edges: string;
  traffic: string;
}

export interface GraphNode {
  code: string;
  name: string;
  kind: "cabecera" | "municipio" | "cruce" | "";
  lat: number;
  lng: number;
}

export interface GraphEdge {
  from: string;
  to: string;
  road: string;
}

export interface NetworkResponse {
  nodes: GraphNode[];
  edges: GraphEdge[];
  data_source: DataSource;
}

export interface SearchPayload {
  algorithm: "dijkstra" | "astar";
  found: boolean;
  nodes: GraphNode[];
  roads: string[];
  minutes: number | null;
  km: number | null;
  cost: number | null;
  expanded: number;
  pushed: number;
  elapsed_ms: number;
}

export interface Meta {
  data_source: DataSource;
  departure?: string;
  band?: Band;
  band_label?: string;
  day_type?: DayType;
}

export type OrderStatus = "pending" | "assigned" | "in_transit" | "delivered" | "failed" | "canceled";
export type Priority = "low" | "normal" | "high";

export interface NodeRef {
  code: string;
  name: string;
}

export interface Order {
  id: number;
  code: string;
  recipient: string;
  phone: string;
  address: string;
  reference: string;
  latitude: number;
  longitude: number;
  node: NodeRef | null;
  weight_kg: number;
  package_count: number;
  priority: Priority;
  status: OrderStatus;
  status_label: string;
  is_demo: boolean;
  created_at: string;
}

export interface Depot {
  id: number;
  name: string;
  address: string;
  latitude: number;
  longitude: number;
  node: NodeRef | null;
}
