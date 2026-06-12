import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { Sparkles, ArrowRight, Loader2 } from "lucide-react";
import { omniboxRoute } from "@/lib/classify";
import { useIngestYouTube } from "@/hooks/useIngest";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

/**
 * The Today hero input. Classifies on submit: a URL ingests immediately
 * (tracked in the Ingesting panel); anything else routes to Chat as a question.
 */
export function Omnibox({ className }: { className?: string }) {
  const [value, setValue] = useState("");
  const navigate = useNavigate();
  const ingest = useIngestYouTube();

  const submit = () => {
    const { kind, text } = omniboxRoute(value);
    if (kind === "ingest") {
      ingest.mutate({ url: text, languages: ["en"], summary_length: "short" });
      setValue("");
    } else if (kind === "ask") {
      navigate(`/chat?q=${encodeURIComponent(text)}`);
    }
  };

  return (
    <div className={cn("space-y-2", className)}>
      <div className="flex items-center gap-2 rounded-[12px] border border-border bg-surface px-4 py-3 transition-colors focus-within:border-border-strong">
        <Sparkles className="size-5 shrink-0 text-accent" strokeWidth={1.5} />
        <input
          value={value}
          onChange={(e) => setValue(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") submit();
          }}
          placeholder="Paste a YouTube link, or ask Merlin…"
          className="flex-1 bg-transparent text-[15px] text-fg outline-none placeholder:text-fg-subtle"
        />
        <Button onClick={submit} size="sm" disabled={!value.trim() || ingest.isPending}>
          {ingest.isPending ? (
            <Loader2 className="size-4 animate-spin" />
          ) : (
            <ArrowRight className="size-4" />
          )}
          Send
        </Button>
      </div>
      <p className="eyebrow pl-1">
        accepts ▸ YouTube · type a question to ask your library
      </p>
    </div>
  );
}
