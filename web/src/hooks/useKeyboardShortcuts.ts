import { useEffect, useRef } from "react";
import { useNavigate } from "react-router-dom";
import { useUi } from "@/store/ui";

/** True when focus is in a text field — shortcuts are suppressed there. */
function inEditable(el: EventTarget | null): boolean {
  const node = el as HTMLElement | null;
  if (!node) return false;
  const tag = node.tagName;
  return (
    tag === "INPUT" ||
    tag === "TEXTAREA" ||
    tag === "SELECT" ||
    node.isContentEditable
  );
}

// `g` then one of these navigates (PATTERNS §9).
const GO: Record<string, string> = {
  t: "/",
  f: "/feed",
  l: "/library",
  c: "/chat",
  i: "/insights",
};

/** Global, app-level shortcuts. ⌘K lives in CommandPalette; this covers the rest. */
export function useKeyboardShortcuts() {
  const navigate = useNavigate();
  const openAdd = useUi((s) => s.openAdd);
  const setPaletteOpen = useUi((s) => s.setPaletteOpen);
  const pendingG = useRef(false);
  const gTimer = useRef<number | undefined>(undefined);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.metaKey || e.ctrlKey || e.altKey) return;
      if (inEditable(e.target)) return;

      // `g` prefix → wait for the next key.
      if (pendingG.current) {
        pendingG.current = false;
        window.clearTimeout(gTimer.current);
        const dest = GO[e.key.toLowerCase()];
        if (dest) {
          e.preventDefault();
          navigate(dest);
        }
        return;
      }

      switch (e.key) {
        case "g":
          pendingG.current = true;
          gTimer.current = window.setTimeout(() => (pendingG.current = false), 800);
          break;
        case "/":
          e.preventDefault();
          setPaletteOpen(true);
          break;
        case "a":
          e.preventDefault();
          openAdd();
          break;
      }
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [navigate, openAdd, setPaletteOpen]);
}
