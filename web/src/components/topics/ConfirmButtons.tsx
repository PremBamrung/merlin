import { useState } from "react";
import { Layers, RefreshCw } from "lucide-react";
import type { TopicItem } from "@/hooks/useTopics";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogClose,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";

/** The Topics jobs that cost an LLM call per item sit behind these confirms. */

// --------------------------------------------------------------------------- //
// Backfill: fit uncategorised items to EXISTING topics (behind a cost confirm)
// --------------------------------------------------------------------------- //

export function BackfillButton({
  uncat,
  disabled,
  onConfirm,
  label,
}: {
  uncat: number;
  disabled: boolean;
  onConfirm: () => void;
  /** Trigger text; defaults to "Classify N uncategorised". */
  label?: string;
}) {
  const [open, setOpen] = useState(false);
  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button size="sm" variant="secondary" disabled={disabled || uncat === 0}>
          <Layers className="size-4" />
          {label ?? `Classify ${uncat} uncategorised`}
        </Button>
      </DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Classify uncategorised items?</DialogTitle>
          <DialogDescription>
            This fits your {uncat} uncategorised item{uncat === 1 ? "" : "s"} to
            the topics you already have — one LLM call each (~{uncat} calls), which
            costs money. It never touches items you've assigned by hand. New topics
            aren't created here; use “Find topics” for that.
          </DialogDescription>
        </DialogHeader>
        <div className="mt-4 flex justify-end gap-2">
          <DialogClose asChild>
            <Button size="sm" variant="ghost">
              Cancel
            </Button>
          </DialogClose>
          <Button
            size="sm"
            onClick={() => {
              setOpen(false);
              onConfirm();
            }}
          >
            <Layers className="size-4" />
            Classify {uncat}
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}

// --------------------------------------------------------------------------- //
// Full re-scan: re-decide the WHOLE library against the current taxonomy
// (behind a cost confirm — one LLM call per item across the whole corpus)
// --------------------------------------------------------------------------- //

export function ReclassifyAllButton({
  total,
  disabled,
  onConfirm,
}: {
  total: number;
  disabled: boolean;
  onConfirm: () => void;
}) {
  const [open, setOpen] = useState(false);
  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button size="sm" variant="secondary" disabled={disabled}>
          <RefreshCw className="size-4" />
          Re-scan all
        </Button>
      </DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Re-scan your whole library?</DialogTitle>
          <DialogDescription>
            This re-checks every categorised and uncategorised item (up to ~{total}{" "}
            LLM call{total === 1 ? "" : "s"}, which costs money) against your
            current topics, and may move items between topics — use it after adding
            new topics you want applied everywhere. Items you've assigned by hand
            are left alone. To speed it up, raise <code>CLASSIFY_CONCURRENCY</code>.
          </DialogDescription>
        </DialogHeader>
        <div className="mt-4 flex justify-end gap-2">
          <DialogClose asChild>
            <Button size="sm" variant="ghost">
              Cancel
            </Button>
          </DialogClose>
          <Button
            size="sm"
            onClick={() => {
              setOpen(false);
              onConfirm();
            }}
          >
            <RefreshCw className="size-4" />
            Re-scan everything
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}

// --------------------------------------------------------------------------- //
// Per-topic re-scan: re-check a topic's members against the current taxonomy
// (behind a cost confirm, since it costs one LLM call per member and moves items)
// --------------------------------------------------------------------------- //

export function RescanButton({
  topic,
  disabled,
  onConfirm,
}: {
  topic: TopicItem;
  disabled: boolean;
  onConfirm: () => void;
}) {
  const [open, setOpen] = useState(false);
  const n = topic.count;
  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <Tooltip>
        <TooltipTrigger asChild>
          <DialogTrigger asChild>
            <Button
              size="icon-sm"
              variant="ghost"
              disabled={disabled}
              aria-label="Re-scan members"
            >
              <RefreshCw className="size-3.5" />
            </Button>
          </DialogTrigger>
        </TooltipTrigger>
        <TooltipContent>Re-scan items for a better-fitting topic</TooltipContent>
      </Tooltip>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Re-scan “{topic.label}”?</DialogTitle>
          <DialogDescription>
            This re-checks its {n} item{n === 1 ? "" : "s"} against your current
            topics — one LLM call each (~{n} call{n === 1 ? "" : "s"}), which costs
            money — and may move items to a better-fitting topic. Items you've
            assigned by hand are left alone.
          </DialogDescription>
        </DialogHeader>
        <div className="mt-4 flex justify-end gap-2">
          <DialogClose asChild>
            <Button size="sm" variant="ghost">
              Cancel
            </Button>
          </DialogClose>
          <Button
            size="sm"
            onClick={() => {
              setOpen(false);
              onConfirm();
            }}
          >
            <RefreshCw className="size-4" />
            Re-scan {n}
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}
