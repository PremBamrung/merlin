import {
  MessageSquare,
  Library,
  Newspaper,
  LayoutGrid,
  BarChart3,
  type LucideIcon,
} from "lucide-react";

/** The places, in rail order. Chat leads: Merlin is chat-first. `/library/:id`
 *  (the Reader) belongs to Library — NavLink's prefix match does that. */
export type Place = {
  id: "chat" | "library" | "feed" | "topics" | "insights";
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

/** The place a pathname belongs to (for the mobile header title). */
export function placeFor(pathname: string): Place | undefined {
  return PLACES.find((p) => pathname === p.to || pathname.startsWith(`${p.to}/`));
}
