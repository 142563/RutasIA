/** Qué conviene hacer ahora: una sola recomendación, la más urgente primero. */
export interface TodayState {
  pendingOrders: number;
  routesInProgress: number;
  routesPlannedToday: number;
  delayedStops: number;
  pendingReroutes: number;
}

export interface NextStep {
  tone: "action" | "warn" | "ok";
  title: string;
  text: string;
  cta?: { label: string; to: string };
}

const plural = (n: number, one: string, many: string) => `${n} ${n === 1 ? one : many}`;

export function nextStep(s: TodayState): NextStep {
  if (s.pendingReroutes > 0) {
    return {
      tone: "warn",
      title: `${plural(s.pendingReroutes, "conductor tiene", "conductores tienen")} una ruta alternativa por decidir`,
      text: "Hubo un incidente en el camino y el sistema encontró una ruta más rápida.",
      cta: { label: "Ver rutas", to: "/rutas" },
    };
  }
  if (s.delayedStops > 0) {
    return {
      tone: "warn",
      title: `${plural(s.delayedStops, "entrega va", "entregas van")} con retraso`,
      text: "Revisa abajo qué ruta es y cuál es su próxima parada.",
    };
  }
  if (s.pendingOrders > 0) {
    return {
      tone: "action",
      title: `Tienes ${plural(s.pendingOrders, "pedido", "pedidos")} sin ruta`,
      text: "Elige una zona y el sistema propone la ruta más rápida con el tráfico de la hora de salida.",
      cta: { label: "Planificar ahora", to: "/planificar" },
    };
  }
  const active = s.routesInProgress + s.routesPlannedToday;
  if (active > 0) {
    return {
      tone: "ok",
      title: "Todo en orden",
      text: `${plural(active, "ruta", "rutas")} de hoy y ningún pedido esperando.`,
    };
  }
  return {
    tone: "action",
    title: "Empieza registrando un pedido",
    text: "Con la dirección de entrega basta: el sistema lo ubica en el mapa.",
    cta: { label: "Nuevo pedido", to: "/pedidos" },
  };
}
