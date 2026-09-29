import { XIcon } from "lucide-react";
import { Dialog as SheetPrimitive } from "radix-ui";
import * as React from "react";
import { cn } from "@/lib/utils";

/** Panel lateral (p. ej. "Nuevo pedido"). Basado en el Sheet de shadcn/ui. */
export const Sheet = SheetPrimitive.Root;
export const SheetTrigger = SheetPrimitive.Trigger;
export const SheetClose = SheetPrimitive.Close;

export function SheetContent({ className, children, title, description, ...props }:
  React.ComponentProps<typeof SheetPrimitive.Content> & { title: string; description?: string }) {
  return (
    <SheetPrimitive.Portal>
      <SheetPrimitive.Overlay className="fixed inset-0 z-40 bg-ink/20 data-[state=open]:animate-in data-[state=open]:fade-in-0 data-[state=closed]:animate-out data-[state=closed]:fade-out-0" />
      <SheetPrimitive.Content
        className={cn(
          "fixed inset-y-0 right-0 z-50 flex w-full max-w-[440px] flex-col border-l border-line bg-surface data-[state=open]:animate-in data-[state=open]:slide-in-from-right data-[state=closed]:animate-out data-[state=closed]:slide-out-to-right",
          className,
        )}
        {...props}
      >
        <div className="flex items-start justify-between border-b border-line px-6 py-5">
          <div>
            <SheetPrimitive.Title className="text-base font-semibold">{title}</SheetPrimitive.Title>
            {description ? (
              <SheetPrimitive.Description className="mt-1 text-[13px] text-ink-2">{description}</SheetPrimitive.Description>
            ) : (
              <SheetPrimitive.Description className="sr-only">{title}</SheetPrimitive.Description>
            )}
          </div>
          <SheetPrimitive.Close className="rounded-md p-1 text-ink-2 hover:bg-hover hover:text-ink" aria-label="Cerrar">
            <XIcon className="size-4" />
          </SheetPrimitive.Close>
        </div>
        {children}
      </SheetPrimitive.Content>
    </SheetPrimitive.Portal>
  );
}
