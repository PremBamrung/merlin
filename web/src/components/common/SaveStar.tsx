import { useEffect, useRef, useState } from "react";
import { Star } from "lucide-react";
import { leafBurst } from "@/lib/motion";
import { cn } from "@/lib/utils";

/**
 * The ★, shared by every Save control. On the *transition* into saved it
 * fills, pops (`gold-leaf`) and sheds a few flakes of gold leaf — never on
 * mount, so a card that is already saved doesn't pop when you land on it.
 * Unsaving is silent: taking something back doesn't deserve a flourish.
 */
export function SaveStar({ saved, className }: { saved: boolean; className?: string }) {
  const wasSaved = useRef(saved);
  const ref = useRef<SVGSVGElement>(null);
  const [leafing, setLeafing] = useState(false);

  useEffect(() => {
    const justSaved = saved && !wasSaved.current;
    wasSaved.current = saved;
    if (!justSaved) return;
    leafBurst(ref.current);
    setLeafing(true);
    const t = window.setTimeout(() => setLeafing(false), 400);
    return () => window.clearTimeout(t);
  }, [saved]);

  return (
    <Star
      ref={ref}
      className={cn("size-4", saved && "fill-signal text-signal", leafing && "gold-leaf", className)}
    />
  );
}
