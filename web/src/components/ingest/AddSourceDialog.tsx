import { useEffect, useState } from "react";
import { ChevronDown, Loader2 } from "lucide-react";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { useUi } from "@/store/ui";
import { useIngestYouTube } from "@/hooks/useIngest";
import { cn } from "@/lib/utils";

const LENGTHS = ["short", "long"] as const;
const COMMON_LANGS = ["en", "fr", "es", "de", "it", "pt", "ja", "ko", "zh", "ru"];

export function AddSourceDialog() {
  const open = useUi((s) => s.addOpen);
  const setOpen = useUi((s) => s.setAddOpen);
  const prefill = useUi((s) => s.addPrefill);

  const [url, setUrl] = useState("");
  const [length, setLength] = useState<(typeof LENGTHS)[number]>("short");
  const [langs, setLangs] = useState<string[]>(["en", "fr"]);
  const [advanced, setAdvanced] = useState(false);
  const ingest = useIngestYouTube();

  // Reset form whenever the dialog (re)opens, seeding the URL from any prefill.
  // This is a genuine effect: it also resets the mutation (a side-effect), so
  // the synchronous state resets here are intentional, not derived state.
  /* eslint-disable react-hooks/set-state-in-effect */
  useEffect(() => {
    if (open) {
      setUrl(prefill);
      setLength("short");
      setLangs(["en", "fr"]);
      setAdvanced(false);
      ingest.reset();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, prefill]);
  /* eslint-enable react-hooks/set-state-in-effect */

  const toggleLang = (l: string) =>
    setLangs((cur) => (cur.includes(l) ? cur.filter((x) => x !== l) : [...cur, l]));

  const submit = () => {
    if (!url.trim() || ingest.isPending) return;
    ingest.mutate(
      { url: url.trim(), languages: langs.length ? langs : ["en"], summary_length: length },
      { onSuccess: () => setOpen(false) },
    );
  };

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogContent
        onKeyDown={(e) => {
          if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) submit();
        }}
      >
        <DialogHeader>
          <DialogTitle>Add a source</DialogTitle>
          <DialogDescription>
            Paste a YouTube URL — Merlin transcribes and summarizes it.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4">
          <div className="space-y-1.5">
            <label className="eyebrow">YouTube URL</label>
            <Input
              autoFocus
              value={url}
              onChange={(e) => setUrl(e.target.value)}
              onKeyDown={(e) => {
                // Enter in the single-line URL field submits, mirroring the
                // Today omnibox (the ⌘/Ctrl+Enter shortcut still works too).
                if (e.key === "Enter") {
                  e.preventDefault();
                  submit();
                }
              }}
              placeholder="https://www.youtube.com/watch?v=…"
            />
          </div>

          <div className="space-y-1.5">
            <label className="eyebrow">Summary length</label>
            <div className="flex gap-2">
              {LENGTHS.map((l) => (
                <button
                  key={l}
                  onClick={() => setLength(l)}
                  className={cn(
                    "flex-1 rounded-md border px-3 py-1.5 text-[13px] capitalize transition-colors",
                    length === l
                      ? "border-accent-border bg-accent-subtle text-fg"
                      : "border-border text-fg-muted hover:border-border-strong",
                  )}
                >
                  {l}
                </button>
              ))}
            </div>
          </div>

          <div>
            <button
              onClick={() => setAdvanced((v) => !v)}
              className="flex items-center gap-1 text-[13px] text-fg-muted hover:text-fg"
            >
              <ChevronDown
                className={cn("size-3.5 transition-transform", advanced && "rotate-180")}
              />
              Languages you understand
            </button>
            {advanced && (
              <div className="mt-2 flex flex-wrap gap-1.5">
                {COMMON_LANGS.map((l) => (
                  <button
                    key={l}
                    onClick={() => toggleLang(l)}
                    className={cn(
                      "rounded-md border px-2.5 py-1 font-mono text-[11px] uppercase transition-colors",
                      langs.includes(l)
                        ? "border-accent-border bg-accent-subtle text-accent-lit"
                        : "border-border text-fg-subtle hover:border-border-strong",
                    )}
                  >
                    {l}
                  </button>
                ))}
              </div>
            )}
          </div>

          {ingest.isError && (
            <p className="text-[13px] text-fail">{(ingest.error as Error).message}</p>
          )}
        </div>

        <div className="flex justify-end gap-2 pt-1">
          <Button variant="ghost" onClick={() => setOpen(false)}>
            Cancel
          </Button>
          <Button onClick={submit} disabled={!url.trim() || ingest.isPending}>
            {ingest.isPending && <Loader2 className="size-4 animate-spin" />}
            Summarize
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}
