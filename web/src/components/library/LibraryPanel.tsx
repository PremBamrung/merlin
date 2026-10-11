import { Link } from "react-router-dom";
import { Library as LibraryIcon, PlayCircle, Star, Tag } from "lucide-react";
import { PanelSlot } from "@/components/layout/panel";
import {
  ChannelAvatar,
  PanelLink,
  PanelSearch,
  PanelSection,
} from "@/components/layout/PanelParts";
import { useItems } from "@/hooks/useItems";
import { useLibraryCount, useSourceTypes } from "@/hooks/useMeta";
import { useUnreadCount } from "@/hooks/useFeed";
import { useTopics, useUncategorisedCount } from "@/hooks/useTopics";
import { useTopChannels } from "@/hooks/useInsights";
import {
  UNCATEGORISED,
  libraryHref,
  sameView,
  viewOf,
  type LibraryView,
} from "@/lib/libraryView";
import { thousands } from "@/lib/format";

const SOURCE_LABEL: Record<string, string> = { youtube: "YouTube" };
const SOURCE_ICON: Record<string, typeof PlayCircle> = { youtube: PlayCircle };

/**
 * The Library place's context panel (mockup `libraryPanel`): views, topics,
 * channels, sources. Each row navigates to `/library?…`, so it works from the
 * Reader too (`params` = null there: nothing is marked current).
 */
export function LibraryPanel({ params }: { params: URLSearchParams | null }) {
  const total = useLibraryCount().data;
  const unread = useUnreadCount().data ?? 0;
  const saved = useItems({ saved: true, per_page: 1 }).data?.total;
  const topics = useTopics("active").data ?? [];
  const uncat = useUncategorisedCount().data ?? 0;
  const channels = useTopChannels(8).data ?? [];
  const sources = useSourceTypes().data ?? [];

  const current = params ? viewOf(params) : null;
  const row = (view: LibraryView) => ({
    to: libraryHref(view, params),
    on: !!current && sameView(current, view),
  });

  return (
    <PanelSlot title="Library" sub={total != null ? `${thousands(total)} items` : undefined}>
      <PanelSearch placeholder="Search library" />

      <PanelSection title="Views">
        <PanelLink {...row({ kind: "all" })} icon={LibraryIcon} label="All items" count={total} />
        <PanelLink
          {...row({ kind: "unread" })}
          lead={<span className="mx-[5px] size-1.5 shrink-0 rounded-full bg-signal" />}
          label="Unread"
          count={unread}
          gold={unread > 0}
        />
        <PanelLink
          {...row({ kind: "saved" })}
          lead={<Star className="size-4 shrink-0 text-signal" strokeWidth={1.75} />}
          label="Saved"
          count={saved}
        />
      </PanelSection>

      <PanelSection
        title="Topics"
        right={
          <Link to="/topics" className="hover:underline hover:underline-offset-[3px]">
            manage
          </Link>
        }
      >
        {topics.map((t) => (
          <PanelLink key={t.slug} {...row({ kind: "topic", slug: t.slug })} label={t.label} count={t.count} />
        ))}
        {uncat > 0 && (
          <PanelLink
            {...row({ kind: "topic", slug: UNCATEGORISED })}
            icon={Tag}
            label="Uncategorised"
            count={uncat}
          />
        )}
      </PanelSection>

      {channels.length > 0 && (
        <PanelSection title="Channels">
          {channels.map((c) => (
            <PanelLink
              key={c.name}
              {...row({ kind: "channel", name: c.name })}
              lead={<ChannelAvatar name={c.name} />}
              label={c.name}
              count={c.count}
            />
          ))}
        </PanelSection>
      )}

      {sources.length > 0 && (
        <PanelSection title="Sources">
          {sources.map((s) => (
            <PanelLink
              key={s.name}
              {...row({ kind: "source", type: s.name })}
              icon={SOURCE_ICON[s.name] ?? LibraryIcon}
              label={SOURCE_LABEL[s.name] ?? s.name}
              count={s.count}
            />
          ))}
        </PanelSection>
      )}
    </PanelSlot>
  );
}
