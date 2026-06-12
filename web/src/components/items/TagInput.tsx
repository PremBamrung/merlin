import { useState, useRef } from "react";
import { X, Plus } from "lucide-react";
import { cn } from "@/lib/utils";

/**
 * Editable tag pills. Controlled: emits the full next array on every change so
 * the caller can drive an optimistic PATCH. Add via Enter/comma, remove via ×.
 */
export function TagInput({
  tags,
  onChange,
  className,
}: {
  tags: string[];
  onChange: (next: string[]) => void;
  className?: string;
}) {
  const [draft, setDraft] = useState("");
  const [adding, setAdding] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  const commit = () => {
    const t = draft.trim().replace(/^#/, "").toLowerCase();
    if (t && !tags.includes(t)) onChange([...tags, t]);
    setDraft("");
  };

  const remove = (t: string) => onChange(tags.filter((x) => x !== t));

  return (
    <div className={cn("flex flex-wrap items-center gap-1.5", className)}>
      {tags.map((t) => (
        <span
          key={t}
          className="inline-flex items-center gap-1 rounded-[6px] border border-accent-border bg-accent-subtle px-2 py-0.5 font-mono text-[11px] text-accent"
        >
          #{t}
          <button
            onClick={() => remove(t)}
            className="text-accent/70 hover:text-accent"
            aria-label={`Remove ${t}`}
          >
            <X className="size-3" />
          </button>
        </span>
      ))}

      {adding ? (
        <input
          ref={inputRef}
          autoFocus
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" || e.key === ",") {
              e.preventDefault();
              commit();
            } else if (e.key === "Backspace" && !draft && tags.length) {
              remove(tags[tags.length - 1]);
            } else if (e.key === "Escape") {
              setDraft("");
              setAdding(false);
            }
          }}
          onBlur={() => {
            commit();
            setAdding(false);
          }}
          placeholder="tag…"
          className="h-6 w-24 rounded-[6px] border border-border bg-surface px-2 font-mono text-[11px] text-fg outline-none focus:border-border-strong"
        />
      ) : (
        <button
          onClick={() => setAdding(true)}
          className="inline-flex items-center gap-1 rounded-[6px] border border-dashed border-border px-2 py-0.5 font-mono text-[11px] text-fg-subtle transition-colors hover:border-border-strong hover:text-fg-muted"
        >
          <Plus className="size-3" /> add tag
        </button>
      )}
    </div>
  );
}
