import { useEffect, useMemo, useRef, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { ChevronRight, Library, MessageSquare } from "lucide-react";
import { Mark } from "@/components/brand/Mark";
import { Composer } from "@/components/chat/Composer";
import { ThreadList } from "@/components/chat/ThreadList";
import { PanelSlot } from "@/components/layout/panel";
import { useChatThreads } from "@/hooks/useChatThreads";
import { useHome } from "@/hooks/useHome";
import { useItemHref } from "@/hooks/useItemHref";
import type { ChatFilters } from "@/hooks/useAgentChat";
import type { HomeDigest, ListItem } from "@/lib/api/endpoints";
import { formatDuration, relDate, thumbnailUrl, thousands } from "@/lib/format";
import { markVisited, readLastVisit, sinceLabel } from "@/lib/lastVisit";
import { cn, randomId } from "@/lib/utils";

/**
 * The chat-first home (docs/EVERYDAY_AI_PLAN.md § Home, "Since last time"):
 * a greeting and one line on what changed, the big composer, suggestions made
 * from what's new, then the conversation to pick up beside the items that
 * arrived. Asking from here opens a new thread with the question sent.
 */
export default function HomeRoute() {
  const navigate = useNavigate();
  // Read once: the visit you came from. Leaving home is what moves it.
  const [since] = useState(() => readLastVisit());
  useEffect(() => {
    const leave = () => document.visibilityState === "hidden" && markVisited();
    document.addEventListener("visibilitychange", leave);
    return () => {
      document.removeEventListener("visibilitychange", leave);
      markVisited();
    };
  }, []);

  const home = useHome(since.toISOString()).data;
  const n = useChatThreads().data?.length;
  const [input, setInput] = useState("");
  const [filters, setFilters] = useState<ChatFilters>({});
  const composerRef = useRef<HTMLTextAreaElement>(null);
  useEffect(() => composerRef.current?.focus(), []);

  const ask = (q: string) => {
    const text = q.trim();
    if (!text) return;
    navigate(`/chat?thread=${randomId()}&q=${encodeURIComponent(text)}`, {
      state: { filters },
    });
  };

  return (
    <div className="flex min-h-[calc(100dvh-182px)] flex-col md:min-h-[calc(100dvh-64px)]">
      <PanelSlot title="Chats" sub={n != null ? `${n} conversation${n === 1 ? "" : "s"}` : undefined}>
        <ThreadList
          activeId=""
          onSelect={(id) => navigate(`/chat?thread=${id}`)}
          onNew={() => composerRef.current?.focus()}
        />
      </PanelSlot>

      <div className="mx-auto mb-auto mt-[6vh] w-full max-w-[820px] min-[1900px]:max-w-[920px] min-[2200px]:max-w-[1040px] md:mt-[14vh]">
        <div className="flex items-center justify-center gap-3.5">
          <Mark size={40} decorative />
          <h1 className="font-display text-[28px] font-semibold leading-tight tracking-[-0.03em] md:text-[38px] min-[1900px]:text-[44px] min-[2200px]:text-[52px]">
            {greeting()}
          </h1>
        </div>
        <SinceLine since={since} home={home} />

        <div className="mt-5 md:mt-6">
          <Composer
            ref={composerRef}
            big
            value={input}
            onChange={setInput}
            onSubmit={() => ask(input)}
            placeholder="Ask anything, or paste a link to add it to your library…"
            filters={filters}
            setFilters={setFilters}
          />
        </div>

        <Suggestions home={home} onPick={ask} />

        {home && (home.continue_thread || home.strip.length > 0) && (
          <div className="mt-7 grid grid-cols-1 gap-3.5 md:mt-10 md:grid-cols-[minmax(0,1fr)_minmax(0,1.75fr)]">
            {home.continue_thread && <ContinueCard thread={home.continue_thread} />}
            {home.strip.length > 0 && (
              <StripCard
                items={home.strip}
                kind={home.strip_kind}
                count={home.strip_kind === "new" ? home.new_since_count : home.unread_count}
                since={since}
                wide={!home.continue_thread}
              />
            )}
          </div>
        )}
      </div>
    </div>
  );
}

function greeting(now = new Date()): string {
  const h = now.getHours();
  return h < 5 ? "Good evening" : h < 12 ? "Good morning" : h < 18 ? "Good afternoon" : "Good evening";
}

/** "Since yesterday: 10 new videos · Dofus is busy +4 · 1 conversation to pick up". */
function SinceLine({ since, home }: { since: Date; home?: HomeDigest }) {
  if (!home) return <p className="mt-2.5 h-5" />;
  const bits: React.ReactNode[] = [];
  if (home.new_since_count > 0) {
    bits.push(
      <b key="new" className="font-medium text-fg">
        {thousands(home.new_since_count)} new {home.new_since_count === 1 ? "item" : "items"}
      </b>,
    );
  } else {
    bits.push(<span key="none">nothing new</span>);
    if (home.unread_count > 0)
      bits.push(
        <Link key="unread" to="/feed" className="hover:text-fg hover:underline hover:underline-offset-[3px]">
          <b className="font-medium text-fg">{thousands(home.unread_count)} unread</b> in your Feed
        </Link>,
      );
  }
  if (home.busy_topic?.kind === "new" && home.busy_topic.count > 1)
    bits.push(
      <span key="busy">
        {home.busy_topic.label} is busy{" "}
        <span className="font-mono text-[13px] text-signal">+{home.busy_topic.count}</span>
      </span>,
    );
  if (home.continue_thread) bits.push(<span key="cont">1 conversation to pick up</span>);
  return (
    <p className="mt-2.5 text-center text-[14px] leading-5 text-fg-muted md:text-[16px]">
      {sinceLabel(since)}:{" "}
      {bits.map((b, i) => (
        <span key={i}>
          {i > 0 && " · "}
          {b}
        </span>
      ))}
    </p>
  );
}

type Suggestion = { text: string; badge?: string; gold?: boolean };

/** Made from what's new — templated, no LLM call (plan: "no LLM in v1"). */
function Suggestions({ home, onPick }: { home?: HomeDigest; onPick: (q: string) => void }) {
  const items = useMemo<Suggestion[]>(() => {
    const out: Suggestion[] = [];
    const t = home?.busy_topic;
    if (t)
      out.push({
        text: `Catch me up on ${t.label}`,
        badge: `${t.count} ${t.kind === "new" ? "new" : "unread"}`,
        gold: t.kind === "new",
      });
    const saved = home?.saved_revisit?.title;
    if (saved) out.push({ text: `What did my videos say about “${clip(saved, 44)}”?` });
    out.push({ text: "What are the recurring themes across my library?" });
    if (out.length < 4) out.push({ text: "What did I add this week?" });
    return out.slice(0, 4);
  }, [home]);

  return (
    <div className="mt-4 flex flex-col gap-1.5 md:flex-row md:flex-wrap md:justify-center md:gap-2">
      {items.map((s) => (
        <button
          key={s.text}
          onClick={() => onPick(s.text)}
          className="inline-flex min-h-[42px] items-center gap-2 rounded-xl border border-border px-3.5 py-1.5 text-left text-[14px] leading-5 text-fg-muted transition-colors hover:border-border-strong hover:bg-surface hover:text-fg md:min-h-9 md:rounded-full"
        >
          <Library className="size-[15px] shrink-0 text-ui-icon" strokeWidth={1.75} />
          <span className="min-w-0">{s.text}</span>
          {s.badge && (
            <span
              className={cn(
                "ml-auto whitespace-nowrap font-mono text-[11px] font-medium leading-none md:ml-0",
                s.gold ? "text-signal" : "text-fg-subtle",
              )}
            >
              · {s.badge}
            </span>
          )}
        </button>
      ))}
    </div>
  );
}

function clip(s: string, n: number): string {
  return s.length > n ? `${s.slice(0, n - 1).trimEnd()}…` : s;
}

const cardClass =
  "relative block min-w-0 rounded-[14px] border border-border bg-[color-mix(in_srgb,var(--color-surface)_50%,transparent)] px-4 pb-[15px] pt-3.5 text-left text-fg-muted transition-colors";

function Eyebrow({ children, right }: { children: React.ReactNode; right?: React.ReactNode }) {
  return (
    <div className="mb-3 flex items-center gap-2 whitespace-nowrap font-mono text-[11px] font-medium uppercase leading-none tracking-[0.08em] text-fg-subtle">
      {children}
      {right && <span className="ml-auto normal-case tracking-normal">{right}</span>}
    </div>
  );
}

function ContinueCard({ thread }: { thread: NonNullable<HomeDigest["continue_thread"]> }) {
  return (
    <Link
      to={`/chat?thread=${thread.id}`}
      className={cn(cardClass, "hover:border-border-strong hover:bg-surface")}
    >
      <Eyebrow right={<span className="text-fg">{relDate(thread.updated_at)}</span>}>
        <MessageSquare className="size-3.5" /> Continue
      </Eyebrow>
      <p className="line-clamp-2 font-display text-[16px] font-semibold leading-[22px] tracking-[-0.01em] text-fg">
        {thread.title || thread.preview || "Conversation"}
      </p>
      {thread.last_reply && (
        <p className="mt-1.5 line-clamp-2 text-[13.5px] leading-5">{stripMarkers(thread.last_reply)}</p>
      )}
      <p className="mt-3 flex items-center gap-2 font-mono text-[11px] leading-none text-fg-subtle">
        <Mark size={14} decorative />
        {thread.message_count} {thread.message_count === 1 ? "message" : "messages"}
        {thread.source_count > 0 &&
          ` · ${thread.source_count} ${thread.source_count === 1 ? "source" : "sources"}`}
      </p>
    </Link>
  );
}

/** Answer text keeps the agent's `[#id]` markers; they mean nothing here. */
function stripMarkers(s: string): string {
  return s.replace(/\(?\s*\[#?[0-9a-fA-F-]{8,}\]\s*\)?/g, "").replace(/\s+([.,;:!?])/g, "$1");
}

function StripCard({
  items,
  kind,
  count,
  since,
  wide,
}: {
  items: ListItem[];
  kind: "new" | "unread";
  count: number;
  since: Date;
  wide: boolean;
}) {
  const itemHref = useItemHref();
  const label = kind === "new" ? `New ${sinceLabel(since).replace(/^Since /, "since ").replace(/^In /, "in ")}` : "Unread";
  return (
    <div className={cn(cardClass, wide && "md:col-span-2")}>
      <Eyebrow
        right={
          <Link to="/feed" className="inline-flex items-center gap-0.5 text-ui-link hover:underline hover:underline-offset-[3px]">
            Open Feed <ChevronRight className="size-3.5" />
          </Link>
        }
      >
        <span className="size-1.5 rounded-full bg-signal" />
        {label} · <span className="text-signal">{thousands(count)}</span>
      </Eyebrow>
      <div className="no-scrollbar -mx-1 flex gap-2.5 overflow-x-auto px-1 md:grid md:grid-cols-5 md:overflow-visible">
        {items.map((it) => {
          const thumb = thumbnailUrl(it);
          const { to, state } = itemHref(it.id);
          return (
            <Link
              key={it.id}
              to={to}
              state={state}
              className="w-[132px] shrink-0 text-fg-muted transition-colors hover:text-fg md:w-auto"
            >
              <span className="relative block aspect-video overflow-hidden rounded-[7px] bg-surface-2">
                {thumb && <img src={thumb} alt="" loading="lazy" className="size-full object-cover" />}
                {!it.read_at && (
                  <span className="absolute left-1.5 top-1.5 size-2 rounded-full bg-signal shadow-[0_0_0_2px_rgb(0_0_0/0.55)]" />
                )}
                {formatDuration(it.duration) && (
                  <span className="absolute bottom-1 right-1 rounded bg-black/75 px-1 py-0.5 font-mono text-[10px] leading-none text-white">
                    {formatDuration(it.duration)}
                  </span>
                )}
              </span>
              <span className="mt-[7px] line-clamp-2 text-[12px] leading-4">{it.title}</span>
            </Link>
          );
        })}
      </div>
    </div>
  );
}
