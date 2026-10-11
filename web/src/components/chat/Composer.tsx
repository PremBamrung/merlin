import { forwardRef, useMemo, type ReactNode } from "react";
import { ArrowUp, Library, Link2, Loader2, Paperclip, Square, X } from "lucide-react";
import type { ChatFilters } from "@/hooks/useAgentChat";
import { useTags, useSourceTypes } from "@/hooks/useMeta";
import { useIngestYouTube } from "@/hooks/useIngest";
import { AutoGrowTextarea } from "@/components/common/AutoGrowTextarea";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { looksLikeUrl } from "@/lib/classify";
import { cn } from "@/lib/utils";

/**
 * The composer card (docs/EVERYDAY_AI_PLAN.md § Composer; mockup `.composer`):
 * the text area over a toolbar — attach, the Library scope, then the round
 * send that turns into Stop while an answer streams. Pasting a link turns the
 * message into "Add to library": Enter ingests it instead of asking.
 *
 * Not here yet, on purpose: the Web toggle and the model menu arrive with
 * Phase 1 (decision O5: hidden until then); attachments with Phase 2.
 */
export const Composer = forwardRef<
  HTMLTextAreaElement,
  {
    value: string;
    onChange: (value: string) => void;
    onSubmit: () => void;
    onStop?: () => void;
    streaming?: boolean;
    placeholder?: string;
    filters: ChatFilters;
    setFilters: (f: ChatFilters) => void;
    /** Right of the toolbar, before send — the context meter. */
    meter?: ReactNode;
    /** The home/idle size: a taller text area. */
    big?: boolean;
  }
>(function Composer(
  { value, onChange, onSubmit, onStop, streaming, placeholder, filters, setFilters, meter, big },
  ref,
) {
  const ingest = useIngestYouTube();
  const isUrl = looksLikeUrl(value);
  const canSend = !!value.trim() && !streaming && !ingest.isPending;

  const submit = () => {
    if (!canSend) return;
    if (isUrl) {
      ingest.mutate(
        { url: value.trim(), languages: ["en", "fr"], summary_length: "short" },
        { onSuccess: () => onChange("") },
      );
      return;
    }
    onSubmit();
  };

  return (
    <div className="rounded-[18px] border border-border-strong bg-surface shadow-[0_1px_0_rgb(255_255_255/0.04)_inset,0_8px_24px_rgb(0_0_0/0.5)] transition-[border-color,box-shadow] duration-150 focus-within:border-ui-focus-border focus-within:shadow-[0_1px_0_rgb(255_255_255/0.04)_inset,0_8px_24px_rgb(0_0_0/0.5),0_0_0_4px_var(--color-ui-focus-ring)]">
      {(isUrl || hasFilters(filters)) && (
        <div className="flex flex-wrap items-center gap-1.5 px-4 pt-3.5">
          {isUrl ? (
            <Token icon={<Link2 className="size-3.5 text-ui-token-icon" />}>Add to library</Token>
          ) : (
            <ScopeTokens filters={filters} setFilters={setFilters} />
          )}
        </div>
      )}
      <AutoGrowTextarea
        ref={ref}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === "Enter" && !e.shiftKey) {
            e.preventDefault();
            submit();
          }
        }}
        rows={big ? 3 : 1}
        placeholder={placeholder}
        aria-label="Message"
        className={cn(
          "block max-h-60 w-full resize-none bg-transparent px-[18px] pb-1.5 pt-4 text-[16px] leading-6 text-fg outline-none placeholder:text-fg-subtle",
          big ? "min-h-[92px]" : "min-h-16",
        )}
      />
      <div className="flex items-center gap-1.5 px-2.5 pb-2.5 pt-2">
        <button
          disabled
          aria-label="Attach (coming soon)"
          title="Attachments arrive soon"
          className="grid size-[30px] place-items-center rounded-md text-fg-subtle disabled:opacity-50"
        >
          <Paperclip className="size-[18px]" />
        </button>
        <LibraryScope filters={filters} setFilters={setFilters} />
        <span className="flex-1" />
        {meter}
        {streaming ? (
          <button
            onClick={onStop}
            aria-label="Stop"
            title="Stop (Esc)"
            className="grid size-[34px] shrink-0 place-items-center rounded-full bg-ui-primary text-ui-primary-fg transition-colors hover:bg-ui-primary-hover"
          >
            <Square className="size-3.5 fill-current" />
          </button>
        ) : (
          <button
            onClick={submit}
            disabled={!canSend}
            aria-label={isUrl ? "Add to library" : "Send"}
            className="grid size-[34px] shrink-0 place-items-center rounded-full bg-ui-primary text-ui-primary-fg transition-[background,transform,opacity] hover:bg-ui-primary-hover disabled:opacity-40 [@media(pointer:fine)]:enabled:hover:-translate-y-px"
          >
            {ingest.isPending ? (
              <Loader2 className="size-4 animate-spin" />
            ) : (
              <ArrowUp className="size-[17px]" strokeWidth={2.2} />
            )}
          </button>
        )}
      </div>
    </div>
  );
});

function hasFilters(f: ChatFilters): boolean {
  return (f.source_types?.length ?? 0) + (f.tags?.length ?? 0) > 0;
}

function Token({ icon, children }: { icon?: ReactNode; children: ReactNode }) {
  return (
    <span className="inline-flex h-[26px] items-center gap-1.5 rounded-[7px] border border-ui-token-border bg-ui-token-bg px-[9px] font-mono text-[12px] font-medium leading-none text-fg">
      {icon}
      {children}
    </span>
  );
}

/** The active library scope as removable tokens over the text area. */
function ScopeTokens({
  filters,
  setFilters,
}: {
  filters: ChatFilters;
  setFilters: (f: ChatFilters) => void;
}) {
  const sources = filters.source_types ?? [];
  const tags = filters.tags ?? [];
  const chip = (label: string, onRemove: () => void) => (
    <button
      key={label}
      onClick={onRemove}
      className="inline-flex h-[26px] items-center gap-1.5 rounded-[7px] border border-ui-token-border bg-ui-token-bg px-[9px] font-mono text-[12px] font-medium leading-none text-fg transition-colors hover:border-border-strong"
      aria-label={`Remove ${label}`}
    >
      {label} <X className="size-3 text-ui-token-icon" />
    </button>
  );
  return (
    <>
      {sources.map((s) =>
        chip(s, () => setFilters({ ...filters, source_types: sources.filter((x) => x !== s) })),
      )}
      {tags.map((t) =>
        chip(`#${t}`, () => setFilters({ ...filters, tags: tags.filter((x) => x !== t) })),
      )}
    </>
  );
}

/**
 * The Library toggle. Library answers are the only kind until Phase 1 adds
 * general + web answers, so it is always on; what it opens is the scope —
 * which source types and tags the agent may search.
 */
function LibraryScope({
  filters,
  setFilters,
}: {
  filters: ChatFilters;
  setFilters: (f: ChatFilters) => void;
}) {
  const tags = useTags();
  const sourceTypes = useSourceTypes();
  const topTags = useMemo(() => (tags.data ?? []).slice(0, 20), [tags.data]);
  const active = (filters.source_types?.length ?? 0) + (filters.tags?.length ?? 0);

  const toggle = (key: "source_types" | "tags", name: string) => {
    const cur = filters[key] ?? [];
    setFilters({
      ...filters,
      [key]: cur.includes(name) ? cur.filter((x) => x !== name) : [...cur, name],
    });
  };
  const chip = (on: boolean) =>
    cn(
      "rounded-full border px-2.5 py-1 text-[12px] transition-colors",
      on
        ? "border-ui-toggle-on-border bg-ui-toggle-on-bg text-ui-toggle-on-fg"
        : "border-border text-fg-muted hover:border-border-strong",
    );

  return (
    <Popover>
      <PopoverTrigger asChild>
        <button
          className="inline-flex h-[30px] items-center gap-1.5 rounded-full border border-ui-toggle-on-border bg-ui-toggle-on-bg px-2.5 text-[13px] text-ui-toggle-on-fg transition-colors hover:border-border-strong"
          title="Answer from your library — choose what it searches"
        >
          <Library className="size-[15px] text-ui-toggle-on-icon" strokeWidth={1.75} />
          Library
          {active > 0 && (
            <span className="font-mono text-[11px] tabular-nums text-fg-muted">· {active}</span>
          )}
        </button>
      </PopoverTrigger>
      <PopoverContent align="start" side="top" className="w-72 space-y-4">
        <p className="text-[12.5px] leading-snug text-fg-muted">
          Merlin answers from your library. Narrow what it searches:
        </p>
        <div className="space-y-2">
          <p className="eyebrow">Source types</p>
          <div className="flex flex-wrap gap-1.5">
            {(sourceTypes.data ?? []).map((s) => (
              <button
                key={s.name}
                onClick={() => toggle("source_types", s.name)}
                className={cn(chip((filters.source_types ?? []).includes(s.name)), "capitalize")}
              >
                {s.name}
              </button>
            ))}
          </div>
        </div>
        {topTags.length > 0 && (
          <div className="space-y-2">
            <p className="eyebrow">Tags</p>
            <div className="flex flex-wrap gap-1.5">
              {topTags.map((t) => (
                <button
                  key={t.name}
                  onClick={() => toggle("tags", t.name)}
                  className={cn(chip((filters.tags ?? []).includes(t.name)), "font-mono text-[11px]")}
                >
                  #{t.name}
                </button>
              ))}
            </div>
          </div>
        )}
        {active > 0 && (
          <button
            onClick={() => setFilters({})}
            className="text-[12px] text-fg-subtle underline-offset-2 hover:text-fg hover:underline"
          >
            Search everything
          </button>
        )}
      </PopoverContent>
    </Popover>
  );
}
