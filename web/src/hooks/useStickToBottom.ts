import { useCallback, useEffect, useRef } from "react";

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
  }, []);

  useEffect(() => {
    const el = scrollRef.current;
    if (!el) return;
    el.addEventListener("scroll", onScroll, { passive: true });
    return () => el.removeEventListener("scroll", onScroll);
  }, [onScroll]);

  useEffect(() => {
    if (stick.current) {
      bottomRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
    }
  }, [dep]);

  return { scrollRef, bottomRef };
}
