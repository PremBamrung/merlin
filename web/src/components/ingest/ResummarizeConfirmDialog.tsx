import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { ArrowUpToLine, RefreshCw, Loader2 } from "lucide-react";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { resummarize, surfaceItem } from "@/lib/api/endpoints";
import { keys } from "@/lib/queryKeys";
import { useActiveTasks } from "@/store/tasks";
import { useUi } from "@/store/ui";
import { toast } from "@/components/ui/toaster";

/**
 * Global confirmation shown when an ingest targets a video that's already in
 * the library. Two ways to make it fresh again: "Bring to top" keeps the
 * summary and just surfaces it (top of Newest, back in the Feed); "Redo
 * summary" re-summarises from the stored transcript (no re-download) using the
 * length/languages the user picked when submitting. X / Esc leaves it alone.
 * Driven by `resummarizePrompt` in the UI store (set by `useIngestYouTube`).
 */
export function ResummarizeConfirmDialog() {
  const prompt = useUi((s) => s.resummarizePrompt);
  const close = useUi((s) => s.closeResummarizePrompt);
  const qc = useQueryClient();
  const addTask = useActiveTasks((s) => s.add);
  const navigate = useNavigate();

  const surface = useMutation({
    mutationFn: () => {
      if (!prompt) throw new Error("No item to bring to top");
      return surfaceItem(prompt.itemId);
    },
    onSuccess: (item) => {
      // keys.items() covers the Library and the home strip.
      qc.invalidateQueries({ queryKey: keys.items() });
      qc.invalidateQueries({ queryKey: keys.item(item.id) });
      qc.invalidateQueries({ queryKey: keys.feed() });
      qc.invalidateQueries({ queryKey: keys.unreadCount() });
      qc.invalidateQueries({ queryKey: keys.topics() });
      toast.success("Back on top", {
        description: "Top of your library and back in the Feed.",
        action: { label: "Open", onClick: () => navigate(`/library/${item.id}`) },
      });
      close();
    },
    onError: (err: Error) =>
      toast.error("Couldn't bring it to the top", { description: err.message }),
  });

  const redo = useMutation({
    mutationFn: () => {
      if (!prompt) throw new Error("No item to re-summarize");
      return resummarize(prompt.itemId, {
        summary_length: prompt.summary_length,
        languages: prompt.languages,
      });
    },
    onSuccess: ({ task_id }) => {
      addTask(task_id);
      qc.invalidateQueries({ queryKey: keys.tasks() });
      toast.success("Re-summarizing…", {
        description: `Tracking task ${task_id.slice(0, 8)}…`,
      });
      close();
    },
    onError: (err: Error) =>
      toast.error("Couldn't re-summarize", { description: err.message }),
  });

  const busy = surface.isPending || redo.isPending;

  return (
    <Dialog open={!!prompt} onOpenChange={(o) => !o && close()}>
      <DialogContent className="max-w-sm">
        <DialogHeader>
          <DialogTitle>Already in your library</DialogTitle>
          <DialogDescription>
            “{prompt?.title ?? "This video"}” has already been ingested. Bring it
            back to the top with its current summary, or redo the summary from
            the stored transcript?
          </DialogDescription>
        </DialogHeader>
        <div className="flex justify-end gap-2 pt-1">
          <Button variant="outline" onClick={() => surface.mutate()} disabled={busy}>
            {surface.isPending ? (
              <Loader2 className="size-4 animate-spin" />
            ) : (
              <ArrowUpToLine className="size-4" />
            )}
            Bring to top
          </Button>
          <Button onClick={() => redo.mutate()} disabled={busy}>
            {redo.isPending ? (
              <Loader2 className="size-4 animate-spin" />
            ) : (
              <RefreshCw className="size-4" />
            )}
            Redo summary
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}
