import { useCallback, useEffect, useRef, useState } from "react";

/** Within this many px of the bottom counts as "pinned to the bottom". */
const THRESHOLD = 80;

/**
 * Auto-scroll a streaming message list to the bottom — but only while the user
 * is already pinned there. The moment they scroll *up* to read, sticking is
 * suspended; it re-engages once they scroll back near the bottom. This stops
 * streaming tokens from yanking the viewport down while the user is reading.
 *
 * Attach `scrollRef` to the scrollable container and `bottomRef` to a sentinel
 * at the end of the list, and pass the streaming value (`messages`) as `dep` so
 * each new chunk re-triggers the scroll.
 *
 * Stickiness is decided by detecting genuine *upward* movement (user intent)
 * rather than by absolute position. Programmatic scrolls and content growth only
 * ever move the viewport down, so they never spuriously un-stick — which a naive
 * "distance from bottom" check would do whenever the smooth-scroll animation
 * lags behind fast tokens.
 */
export function useStickToBottom<T>(dep: T) {
  const scrollRef = useRef<HTMLDivElement>(null);
  const bottomRef = useRef<HTMLDivElement>(null);
  const stick = useRef(true);
  const prevTop = useRef(0);
  // A render-visible mirror of `stick`, so callers can show a "jump to latest"
  // affordance while the user is reading above the fold (`stick` is a ref and
  // never re-renders on its own).
  const [pinned, setPinned] = useState(true);

  /** Jump to the bottom and re-engage sticking (used on send / the jump button). */
  const scrollToBottom = useCallback(() => {
    stick.current = true;
    setPinned(true);
    bottomRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, []);

  const onScroll = useCallback(() => {
    const el = scrollRef.current;
    if (!el) return;
    const top = el.scrollTop;
    const distance = el.scrollHeight - top - el.clientHeight;
    if (top < prevTop.current - 2 && distance > THRESHOLD) {
      stick.current = false; // user scrolled up to read — let them
    } else if (distance < THRESHOLD) {
      stick.current = true; // back near the bottom — resume following
    }
    prevTop.current = top;
    setPinned(stick.current);
  }, []);

  useEffect(() => {
    const el = scrollRef.current;
    if (!el) return;
    el.addEventListener("scroll", onScroll, { passive: true });
    return () => el.removeEventListener("scroll", onScroll);
  }, [onScroll]);

  useEffect(() => {
    if (stick.current) {
      // Instant (not smooth) — this fires on every streamed token; a smooth
      // animation re-triggered dozens of times a second fights itself and janks.
      // Smooth scrolling is reserved for the explicit `scrollToBottom` jump.
      bottomRef.current?.scrollIntoView({ behavior: "auto", block: "end" });
    }
  }, [dep]);

  return { scrollRef, bottomRef, pinned, scrollToBottom };
}
