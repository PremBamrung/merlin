import { useEffect, useRef, useState } from "react";
import { Check, Copy } from "lucide-react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

/**
 * Copy-to-clipboard button with a transient ✓ confirmation. Defaults to a
 * ghost icon button; pass `label` for a labelled variant (e.g. "Copy").
 */
export function CopyButton({
  text,
  label,
  className,
  size = "icon-sm",
}: {
  text: string;
  label?: string;
  className?: string;
  size?: "icon-sm" | "sm";
}) {
  const [copied, setCopied] = useState(false);
  const timer = useRef<number | undefined>(undefined);

  useEffect(() => () => window.clearTimeout(timer.current), []);

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
      window.clearTimeout(timer.current);
      timer.current = window.setTimeout(() => setCopied(false), 1500);
    } catch {
      /* clipboard unavailable (e.g. insecure context) — no-op */
    }
  };

  const Icon = copied ? Check : Copy;

  return (
    <Button
      variant="ghost"
      size={label ? "sm" : size}
      onClick={copy}
      className={cn(copied && "text-accent", className)}
      aria-label={label ?? "Copy"}
    >
      <Icon className="size-3.5" />
      {label && (copied ? "Copied" : label)}
    </Button>
  );
}
