import { useMutation, useQueryClient } from "@tanstack/react-query";
import { RefreshCw, Loader2 } from "lucide-react";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { resummarize } from "@/lib/api/endpoints";
import { keys } from "@/lib/queryKeys";
import { useActiveTasks } from "@/store/tasks";
import { useUi } from "@/store/ui";
import { toast } from "@/components/ui/toaster";

/**
 * Global confirmation shown when an ingest targets a video that's already in
 * the library. Instead of silently redoing the summary, we ask first; on
 * confirm we re-summarise from the stored transcript (no re-download) using the
 * length/languages the user picked when submitting. Driven by `resummarizePrompt`
 * in the UI store (set by `useIngestYouTube`).
 */
export function ResummarizeConfirmDialog() {
  const prompt = useUi((s) => s.resummarizePrompt);
  const close = useUi((s) => s.closeResummarizePrompt);
  const qc = useQueryClient();
  const addTask = useActiveTasks((s) => s.add);

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

  return (
    <Dialog open={!!prompt} onOpenChange={(o) => !o && close()}>
      <DialogContent className="max-w-sm">
        <DialogHeader>
          <DialogTitle>Already in your library</DialogTitle>
          <DialogDescription>
            “{prompt?.title ?? "This video"}” has already been ingested. Would you
            like to redo the summary from the stored transcript?
          </DialogDescription>
        </DialogHeader>
        <div className="flex justify-end gap-2 pt-1">
          <Button variant="ghost" onClick={close} disabled={redo.isPending}>
            Keep existing
          </Button>
          <Button onClick={() => redo.mutate()} disabled={redo.isPending}>
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
