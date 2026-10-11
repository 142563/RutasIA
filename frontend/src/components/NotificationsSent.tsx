import { ChevronRightIcon } from "lucide-react";
import { StatusDot } from "@/components/ui/misc";
import {
  NOTIFICATION_STATUS, notificationLine, notificationWhen, useNotifications, type NotificationsFilter,
} from "@/lib/notifications";

/** "Avisos enviados": lista compacta y plegable de los correos de una ruta o de un pedido. */
export function NotificationsSent({ filter }: { filter: NotificationsFilter }) {
  const query = useNotifications(filter);
  // Solo admin y despachador pueden verla: si el servidor la niega, la sección simplemente no aparece
  if (query.error) return null;
  const items = query.data ?? [];

  return (
    <section aria-label="Avisos enviados">
      <details className="group">
        <summary className="flex cursor-pointer list-none items-center gap-1.5 text-sm font-semibold">
          <ChevronRightIcon className="size-4 text-ink-2 transition-transform group-open:rotate-90" aria-hidden />
          Avisos enviados {query.data ? <span className="num font-normal text-ink-2">{items.length}</span> : null}
        </summary>
        {query.isPending ? <p className="mt-3 text-[13px] text-ink-2">Cargando…</p> : null}
        {query.data && items.length === 0 ? <p className="mt-3 text-[13px] text-ink-2">Todavía no se envió ningún aviso.</p> : null}
        {items.length > 0 ? (
          <ul className="mt-3 divide-y divide-line border-y border-line">
            {items.map((n) => {
              const status = NOTIFICATION_STATUS[n.status];
              return (
                <li key={n.id} className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1 py-2.5 text-[13px]">
                  <span className="min-w-0 break-words text-ink-3">{notificationLine(n)}</span>
                  <span className="flex shrink-0 items-center gap-3">
                    <StatusDot color={status.color}>{status.label}</StatusDot>
                    <span className="num text-ink-2">{notificationWhen(n.created_at)}</span>
                  </span>
                </li>
              );
            })}
          </ul>
        ) : null}
      </details>
    </section>
  );
}
