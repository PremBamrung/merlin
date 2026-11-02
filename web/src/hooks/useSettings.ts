import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import {
  getSettings,
  getSettingsModels,
  updateSettings,
  type AppSettings,
  type SettingsPatch,
} from "@/lib/api/endpoints";
import { keys } from "@/lib/queryKeys";

export function useSettings() {
  return useQuery({ queryKey: keys.settings(), queryFn: getSettings });
}

/** The proxy's model aliases — fetched live, so cached briefly. */
export function useSettingsModels(enabled = true) {
  return useQuery({
    queryKey: keys.settingsModels(),
    queryFn: getSettingsModels,
    staleTime: 5 * 60_000,
    enabled,
  });
}

/** Apply `patch` with the new values; resetting (`null`) shows the default. */
function applyPatch(page: AppSettings, patch: SettingsPatch): AppSettings {
  return {
    ...page,
    sections: page.sections.map((s) => ({
      ...s,
      settings: s.settings.map((k) =>
        k.key in patch
          ? patch[k.key] === null
            ? { ...k, value: k.default, overridden: false }
            : { ...k, value: patch[k.key], overridden: true }
          : k,
      ),
    })),
  };
}

/** Save-on-change: optimistic, rolled back with a toast if the server refuses. */
export function useUpdateSettings() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (patch: SettingsPatch) => updateSettings(patch),
    onMutate: async (patch) => {
      await qc.cancelQueries({ queryKey: keys.settings(), exact: true });
      const prev = qc.getQueryData<AppSettings>(keys.settings());
      if (prev) qc.setQueryData<AppSettings>(keys.settings(), applyPatch(prev, patch));
      return { prev };
    },
    onError: (err: Error, _patch, ctx) => {
      if (ctx?.prev) qc.setQueryData(keys.settings(), ctx.prev);
      toast.error("Couldn't save setting", { description: err.message });
    },
    onSuccess: (page, patch) => {
      qc.setQueryData(keys.settings(), page);
      const reset = Object.values(patch).every((v) => v === null);
      toast.success(reset ? "Reset to default" : "Setting saved", {
        description: "Applies from the next request.",
      });
    },
  });
}
