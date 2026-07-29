import { useEffect, useRef, useState } from "react";
import { Check, Copy } from "lucide-react";
import { Button } from "@/components/ui/button";
import { toast } from "@/components/ui/toaster";
import { cn } from "@/lib/utils";

/**
 * Copy `text` to the clipboard. Uses the async Clipboard API when available
 * (HTTPS or localhost), and falls back to the legacy `execCommand("copy")` for
 * **insecure contexts** — plain HTTP over a non-localhost host, e.g. accessing
 * the app via a LAN IP or a Tailscale hostname, where `navigator.clipboard` is
 * `undefined`. Throws if neither path succeeds so callers can surface an error.
 */
async function copyText(text: string): Promise<void> {
  if (navigator.clipboard?.writeText) {
    await navigator.clipboard.writeText(text);
    return;
  }
  const ta = document.createElement("textarea");
  ta.value = text;
  ta.style.position = "fixed";
  ta.style.opacity = "0";
  document.body.appendChild(ta);
  ta.focus();
  ta.select();
  try {
    if (!document.execCommand("copy")) throw new Error("execCommand copy failed");
  } finally {
    ta.remove();
  }
}

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
      await copyText(text);
      setCopied(true);
      window.clearTimeout(timer.current);
      timer.current = window.setTimeout(() => setCopied(false), 1500);
    } catch {
      toast.error("Couldn't copy — try selecting the text manually.");
    }
  };

  const Icon = copied ? Check : Copy;

  return (
    <Button
      variant="ghost"
      size={label ? "sm" : size}
      onClick={copy}
      className={cn(copied && "text-success", className)}
      aria-label={label ?? "Copy"}
    >
      <Icon className="size-3.5" />
      {label && (copied ? "Copied" : label)}
    </Button>
  );
}
