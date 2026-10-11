/** Avisos enviados por correo (bitácora): para el detalle de una ruta o de un pedido. */
import { useQuery } from "@tanstack/react-query";
import { api } from "./api";

export type NotificationStatus = "sent" | "failed" | "skipped";

export interface SentNotification {
  id: number;
  event: string;
  event_label: string;
  /** Ya viene enmascarado desde el servidor ("j***@gmail.com") */
  recipient: string;
  audience: "customer" | "staff";
  audience_label: string;
  status: NotificationStatus;
  status_label: string;
  created_at: string;
}

export const NOTIFICATION_STATUS: Record<NotificationStatus, { label: string; color: string }> = {
  sent: { label: "Enviado", color: "var(--color-ok)" },
  failed: { label: "Falló", color: "var(--color-err)" },
  skipped: { label: "Sin enviar", color: "var(--color-ink-2)" },
};

/** Filtro del endpoint: exactamente uno de los dos. */
export type NotificationsFilter = { route: number } | { order: number };

export function useNotifications(filter: NotificationsFilter, enabled = true) {
  return useQuery({
    queryKey: ["notifications", filter],
    queryFn: () => api<{ notifications: SentNotification[] }>("/api/v2/notifications/", { query: filter }),
    select: (data) => data.notifications,
    enabled,
    retry: false,
  });
}

/** "Pedido entregado · Cliente · j***@gmail.com": la línea que se lee de corrido. */
export function notificationLine(n: Pick<SentNotification, "event_label" | "audience_label" | "recipient">): string {
  return `${n.event_label} · ${n.audience_label} · ${n.recipient}`;
}

/** "11 oct, 14:32" en hora de Guatemala. */
export function notificationWhen(iso: string): string {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return "";
  return new Intl.DateTimeFormat("es-GT", {
    day: "numeric", month: "short", hour: "2-digit", minute: "2-digit", hour12: false, timeZone: "America/Guatemala",
  }).format(date);
}
