import { NavLink, useLocation } from "react-router-dom";
import { Menu } from "lucide-react";
import { PLACES, isCurrent } from "./places";
import { useUnreadCount } from "@/hooks/useFeed";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { cn } from "@/lib/utils";

/** Phone navigation (mockup `.tabs`): the first four places + More. */
const TABBED = PLACES.slice(0, 4);
const MORE = PLACES.slice(4);

const tabClass = (on: boolean) =>
  cn(
    "relative flex flex-1 flex-col items-center justify-center gap-[3px] rounded-[10px] text-[10.5px] font-medium leading-3",
    on
      ? "text-fg before:absolute before:-top-[7px] before:left-[30%] before:right-[30%] before:h-0.5 before:rounded-sm before:bg-ui-current-bar"
      : "text-fg-subtle",
  );

export function BottomTabs() {
  const unread = useUnreadCount().data ?? 0;
  const { pathname } = useLocation();
  const moreOn = MORE.some((p) => pathname.startsWith(p.to));

  return (
    <nav
      aria-label="Places"
      className="sticky bottom-0 z-30 flex h-[62px] shrink-0 gap-0.5 border-t border-border bg-ui-rail-bg/95 px-1.5 pb-2 pt-1.5 backdrop-blur-md"
    >
      {TABBED.map((p) => (
        <NavLink
          key={p.id}
          to={p.to}
          aria-current={isCurrent(p, pathname) ? "page" : undefined}
          className={() => tabClass(isCurrent(p, pathname))}
        >
          {() => (
            <>
              <p.icon
                className={cn("size-5", isCurrent(p, pathname) && "text-ui-current-fg")}
                strokeWidth={1.75}
              />
              {p.label}
              {p.id === "feed" && unread > 0 && (
                <span className="absolute left-[calc(50%+6px)] top-px h-4 min-w-4 rounded-full bg-signal px-1 text-center font-mono text-[10px] font-semibold leading-4 text-bg">
                  {unread > 99 ? "99+" : unread}
                </span>
              )}
            </>
          )}
        </NavLink>
      ))}
      <DropdownMenu>
        <DropdownMenuTrigger className={tabClass(moreOn)}>
          <Menu className={cn("size-5", moreOn && "text-ui-current-fg")} strokeWidth={1.75} />
          More
        </DropdownMenuTrigger>
        <DropdownMenuContent side="top" align="end" className="mb-2 min-w-40">
          {MORE.map((p) => (
            <DropdownMenuItem key={p.id} asChild>
              <NavLink to={p.to}>
                <p.icon className="size-4" /> {p.label}
              </NavLink>
            </DropdownMenuItem>
          ))}
        </DropdownMenuContent>
      </DropdownMenu>
    </nav>
  );
}
