import { useQuery } from "@tanstack/react-query";
import { api } from "./api";
import type { NetworkResponse } from "./types";

/** Red vial (nodos + tramos). Cambia muy poco: se cachea una hora. */
export function useNetwork() {
  return useQuery({
    queryKey: ["network"],
    queryFn: () => api<NetworkResponse>("/api/routing/nodes/"),
    staleTime: 60 * 60 * 1000,
  });
}

export function isRealData(source: { edges: string; traffic: string } | undefined): boolean {
  if (!source) return false;
  return !/estimate|synthetic|none/.test(`${source.edges} ${source.traffic}`);
}
