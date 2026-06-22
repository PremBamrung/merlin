import * as React from "react";
import { cn } from "@/lib/utils";

/**
 * A textarea that grows with its content instead of scrolling a fixed box.
 * Height is recomputed from `scrollHeight` on every value change; a `max-h-*`
 * class on the element caps the growth (CSS `max-height` wins over the inline
 * height) and `overflow-y-auto` lets it scroll past that cap. Forwards a ref so
 * callers can focus it (composer auto-focus / keyboard shortcuts).
 */
export const AutoGrowTextarea = React.forwardRef<
  HTMLTextAreaElement,
  React.ComponentPropsWithoutRef<"textarea">
>(({ value, className, ...props }, ref) => {
  const innerRef = React.useRef<HTMLTextAreaElement | null>(null);

  const setRefs = React.useCallback(
    (node: HTMLTextAreaElement | null) => {
      innerRef.current = node;
      if (typeof ref === "function") ref(node);
      else if (ref) ref.current = node;
    },
    [ref],
  );

  // Recompute on value change (and on mount): reset to auto so the box can
  // shrink, then lock to the content height.
  React.useLayoutEffect(() => {
    const el = innerRef.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${el.scrollHeight}px`;
  }, [value]);

  return (
    <textarea
      ref={setRefs}
      value={value}
      className={cn("resize-none", className)}
      {...props}
    />
  );
});
AutoGrowTextarea.displayName = "AutoGrowTextarea";
