import { Toaster as Sonner } from "sonner";

/** Themed Sonner toaster — floating elevation, design-system surfaces. */
export function Toaster() {
  return (
    <Sonner
      theme="dark"
      position="bottom-right"
      toastOptions={{
        classNames: {
          toast:
            "!bg-surface-2 !border !border-border-strong !text-fg !rounded-[12px] !shadow-xl !shadow-black/40",
          description: "!text-fg-muted",
          actionButton: "!bg-accent !text-accent-fg",
          cancelButton: "!bg-surface !text-fg-muted",
          error: "!border-accent-border",
          success: "!text-fg",
        },
      }}
    />
  );
}

export { toast } from "sonner";
