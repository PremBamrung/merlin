import { useEffect, useRef, useState } from "react";

/** Nearest ancestor that scrolls vertically — the app scrolls `<main>`, not the
 *  window, and an IntersectionObserver rooted at the viewport can't look past
 *  `<main>`'s clip, so `rootMargin` would never pre-load anything. */
function scrollParent(el: HTMLElement): HTMLElement | null {
  for (let n = el.parentElement; n; n = n.parentElement) {
    const { overflowY } = getComputedStyle(n);
    if (overflowY === "auto" || overflowY === "scroll") return n;
  }
  return null;
}

/**
 * Calls `onReach` when the returned ref's element comes within `margin` px of
 * the scroll container's bottom edge. `active` gates it (no next page, or a
 * fetch already in flight). The observer is re-armed whenever `active` flips
 * back on, so a sentinel still on screen after a short page loads the next one
 * too instead of waiting for a scroll that can't happen.
 */
export function useLoadMoreSentinel(onReach: () => void, active: boolean, margin = 1200) {
  const [node, setNode] = useState<HTMLElement | null>(null);
  const cb = useRef(onReach);
  useEffect(() => {
    cb.current = onReach;
  });

  useEffect(() => {
    if (!node || !active) return;
    const io = new IntersectionObserver(
      (entries) => {
        if (entries.some((e) => e.isIntersecting)) cb.current();
      },
      { root: scrollParent(node), rootMargin: `0px 0px ${margin}px 0px` },
    );
    io.observe(node);
    return () => io.disconnect();
  }, [node, active, margin]);

  return setNode;
}
