import {
  MessageSquare,
  Library,
  Newspaper,
  LayoutGrid,
  BarChart3,
  Settings,
  type LucideIcon,
} from "lucide-react";

/** The places, in rail order. Chat leads: Merlin is chat-first. `/library/:id`
 *  (the Reader) belongs to Library — NavLink's prefix match does that. */
export type Place = {
  id: "chat" | "library" | "feed" | "topics" | "insights" | "settings";
  to: string;
  label: string;
  icon: LucideIcon;
};

export const PLACES: Place[] = [
  { id: "chat", to: "/chat", label: "Chat", icon: MessageSquare },
  { id: "library", to: "/library", label: "Library", icon: Library },
  { id: "feed", to: "/feed", label: "Feed", icon: Newspaper },
  { id: "topics", to: "/topics", label: "Topics", icon: LayoutGrid },
  { id: "insights", to: "/insights", label: "Insights", icon: BarChart3 },
];

/** Settings is a place too, but not one of the rail's top places: it sits at
 *  the rail's foot, in the phone's More menu, and in the palette. */
export const SETTINGS_PLACE: Place = {
  id: "settings",
  to: "/settings",
  label: "Settings",
  icon: Settings,
};

/** Every place, for lookups and lists that include Settings. */
export const ALL_PLACES: Place[] = [...PLACES, SETTINGS_PLACE];

/** The place a pathname belongs to. Home (`/`) is the Chat place's front
 *  door, so it belongs to Chat. */
export function placeFor(pathname: string): Place | undefined {
  if (pathname === "/") return PLACES[0];
  return ALL_PLACES.find((p) => pathname === p.to || pathname.startsWith(`${p.to}/`));
}

/** Whether a place is the current one — NavLink's own match, plus home → Chat. */
export function isCurrent(place: Place, pathname: string): boolean {
  return placeFor(pathname)?.id === place.id;
}
