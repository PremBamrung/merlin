import { RotateCw } from "lucide-react";
import { useOnline } from "@/hooks/useOnline";
import { Button } from "@/components/ui/button";

/**
 * "Can't reach Merlin" (mockup `#offline`). Fixed over the top of the page
 * rather than inserted into it, so losing the connection doesn't shove
 * every route's content down. Cached pages stay browsable underneath.
 */
export function OfflineNotice() {
  const { online, lastContact, checking, retry, retryEvery } = useOnline();
  if (online) return null;
  const last = lastContact
    ? new Date(lastContact).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })
    : null;
  return (
    <div
      role="status"
      className="fixed left-1/2 top-3 z-[60] flex max-w-[calc(100vw-24px)] -translate-x-1/2 items-center gap-3 rounded-xl border border-fail/45 bg-surface-raised py-2 pl-2.5 pr-2 shadow-[0_16px_40px_rgb(0_0_0/0.5),inset_3px_0_0_var(--color-fail)]"
    >
      <span className="rounded-[5px] border border-fail/60 px-1.5 py-0.5 font-mono text-[10.5px] font-medium tracking-[0.08em] text-fail">
        OFFLINE
      </span>
      <span className="min-w-0 text-[14px] text-fg">
        <b className="font-medium">Can't reach Merlin</b>
        <span className="hidden text-fg-muted sm:inline">
          {" "}
          · retrying every {retryEvery}s{last && ` · last contact ${last}`} · is Tailscale connected?
        </span>
      </span>
      <Button size="sm" variant="secondary" onClick={retry} disabled={checking}>
        <RotateCw className={checking ? "size-3.5 animate-spin" : "size-3.5"} /> Retry now
      </Button>
    </div>
  );
}
