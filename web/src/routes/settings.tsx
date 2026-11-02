import { useState, type ReactNode } from "react";
import { Brain, Cpu, MessageSquare, Minus, Plus, RotateCcw } from "lucide-react";
import { useSettings, useSettingsModels, useUpdateSettings } from "@/hooks/useSettings";
import type { AppSettings, ModelOption, SettingItem } from "@/lib/api/endpoints";
import { PanelSlot } from "@/components/layout/panel";
import { PanelButton, PanelSection } from "@/components/layout/PanelParts";
import { Skeleton } from "@/components/ui/skeleton";
import { ErrorState } from "@/components/common/ErrorState";
import { cn } from "@/lib/utils";

/**
 * Settings: the runtime-tunable knobs (merlin.core.tunables). Each knob's
 * default is its .env value; a change here saves at once, overrides it from the
 * next request, and Reset drops the override. Secrets and infrastructure
 * (keys, URLs, provider) stay in .env — they aren't here on purpose.
 */

type SectionId = AppSettings["sections"][number]["id"];

const SECTIONS: Record<SectionId, { title: string; sub: string; icon: typeof Brain }> = {
  thinking: {
    title: "Thinking",
    sub: "How hard the model reasons before it answers. Higher is slower: on Gemini Flash, each step at medium took about 4s longer than at low.",
    icon: Brain,
  },
  chat: {
    title: "Chat",
    sub: "How library chat searches before it answers.",
    icon: MessageSquare,
  },
  models: {
    title: "Models",
    sub: "Which of your LiteLLM proxy's models each job uses.",
    icon: Cpu,
  },
};

const KNOBS: Record<string, { label: string; hint: string }> = {
  summarize_thinking: {
    label: "Summaries",
    hint: "Writing an item's summary when it's added or re-summarised.",
  },
  classify_thinking: {
    label: "Tags & topics",
    hint: "Tagging each item and filing it under topics, after its summary.",
  },
  discover_thinking: {
    label: "Topic discovery",
    hint: "Grouping the library into proposed new topics.",
  },
  search_step_thinking: {
    label: "Chat: choosing searches",
    hint: "Library chat's first step each turn. The answer itself uses the composer's level, and this never raises it.",
  },
  chat_max_requests: {
    label: "Search budget",
    hint: "Model steps a library-chat turn may take before it has to answer with what it found.",
  },
  chat_model: { label: "Chat model", hint: "Library chat and the Reader's chat." },
  ingest_model: {
    label: "Ingest model",
    hint: "Summaries, tags & topics, and topic discovery.",
  },
};

const LEVEL_LABEL: Record<string, string> = {
  minimal: "Minimal",
  low: "Low",
  medium: "Medium",
  high: "High",
};

export default function SettingsRoute() {
  const settings = useSettings();
  const models = useSettingsModels(!!settings.data && settings.data.provider === "litellm");
  const update = useUpdateSettings();

  const save = (key: string, value: string | number | null) => update.mutate({ [key]: value });

  const renderSection = (section: AppSettings["sections"][number]) => (
    <Section key={section.id} id={section.id}>
      {section.id === "thinking" && !settings.data!.thinking_supported && (
        <Note>
          Thinking levels only apply on the LiteLLM provider (now:{" "}
          {settings.data!.provider}).
        </Note>
      )}
      {section.id === "models" && models.data && !models.data.available && (
        <Note>
          Couldn't list the proxy's models
          {settings.data!.provider !== "litellm" && " (the provider isn't LiteLLM)"}, so
          models can't be changed here right now.
        </Note>
      )}
      {section.settings.map((item) => (
        <Row key={item.key} item={item} onReset={() => save(item.key, null)}>
          {item.kind === "thinking" ? (
            <LevelControl
              item={item}
              disabled={!settings.data!.thinking_supported}
              onChange={(v) => save(item.key, v)}
            />
          ) : item.kind === "int" ? (
            <NumberControl item={item} onChange={(v) => save(item.key, v)} />
          ) : (
            <ModelControl
              item={item}
              models={models.data?.available ? models.data.models : null}
              loading={models.isLoading}
              onChange={(v) => save(item.key, v)}
            />
          )}
        </Row>
      ))}
    </Section>
  );

  return (
    <div className="space-y-5">
      <PanelSlot title="Settings">
        <PanelSection title="Sections">
          {(Object.keys(SECTIONS) as SectionId[]).map((id) => (
            <PanelButton
              key={id}
              label={SECTIONS[id].title}
              icon={SECTIONS[id].icon}
              onClick={() =>
                document.getElementById(`settings-${id}`)?.scrollIntoView({ behavior: "smooth" })
              }
            />
          ))}
        </PanelSection>
      </PanelSlot>

      <div className="flex flex-wrap items-end gap-x-4 gap-y-1">
        <h1 className="font-display text-[26px] font-semibold leading-9 tracking-[-0.03em] md:text-[30px]">
          Settings
        </h1>
        <span className="pb-[7px] font-mono text-[12px] text-fg-subtle">
          saves as you change · applies from the next request
        </span>
      </div>

      {settings.error ? (
        <ErrorState error={settings.error as Error} onRetry={() => settings.refetch()} />
      ) : !settings.data ? (
        <div className="grid gap-4 min-[1280px]:grid-cols-2 min-[1900px]:grid-cols-3">
          {[0, 1, 2].map((i) => (
            <Skeleton key={i} className="h-72 rounded-[12px]" />
          ))}
        </div>
      ) : (
        <div className="grid items-start gap-4 min-[1280px]:grid-cols-2 min-[1900px]:grid-cols-3">
          {/* Thinking (the tall one) on its own; Chat + Models stack beside it at
              two columns, and become columns of their own at three. */}
          {settings.data.sections
            .filter((s) => s.id === "thinking")
            .map(renderSection)}
          <div className="flex flex-col gap-4 min-[1900px]:contents">
            {settings.data.sections
              .filter((s) => s.id !== "thinking")
              .map(renderSection)}
          </div>
        </div>
      )}
    </div>
  );
}

function Section({ id, children }: { id: SectionId; children: ReactNode }) {
  const meta = SECTIONS[id];
  return (
    <section
      id={`settings-${id}`}
      aria-labelledby={`settings-${id}-title`}
      className="scroll-mt-4 rounded-[12px] border border-border bg-surface"
    >
      <header className="border-b border-border px-5 pb-4 pt-4">
        <h2
          id={`settings-${id}-title`}
          className="flex items-center gap-2 font-display text-[17px] font-semibold tracking-[-0.01em]"
        >
          <meta.icon className="size-4 text-fg-subtle" strokeWidth={1.75} />
          {meta.title}
        </h2>
        <p className="mt-1 text-[13.5px] leading-5 text-fg-muted">{meta.sub}</p>
      </header>
      <div className="divide-y divide-border">{children}</div>
    </section>
  );
}

function Note({ children }: { children: ReactNode }) {
  return (
    <p className="bg-surface-2 px-5 py-2.5 text-[13px] leading-5 text-fg-muted">{children}</p>
  );
}

function Row({
  item,
  onReset,
  children,
}: {
  item: SettingItem;
  onReset: () => void;
  children: ReactNode;
}) {
  const meta = KNOBS[item.key] ?? { label: item.key, hint: "" };
  const def = item.kind === "thinking" ? LEVEL_LABEL[String(item.default)] : item.default;
  return (
    <div className="flex flex-col gap-3 px-5 py-4 sm:flex-row sm:items-center sm:gap-6">
      <div className="min-w-0 flex-1">
        <p id={`knob-${item.key}`} className="text-[14px] font-medium text-fg">
          {meta.label}
        </p>
        {meta.hint && <p className="mt-0.5 text-[13px] leading-5 text-fg-muted">{meta.hint}</p>}
        <p className="mt-1.5 flex flex-wrap items-center gap-x-2 font-mono text-[11.5px] text-fg-subtle">
          <span className="whitespace-nowrap">
            default {def === "" || def == null ? "model's own" : String(def)}
            {!item.overridden && " · in use"}
          </span>
          {item.overridden && (
            <button
              onClick={onReset}
              className="inline-flex items-center gap-1 rounded text-ui-link hover:underline"
              aria-label={`Reset ${meta.label} to default`}
            >
              <RotateCcw className="size-3" /> reset
            </button>
          )}
        </p>
      </div>
      <div className="shrink-0">{children}</div>
    </div>
  );
}

function LevelControl({
  item,
  disabled,
  onChange,
}: {
  item: SettingItem;
  disabled: boolean;
  onChange: (v: string) => void;
}) {
  return (
    <div
      role="radiogroup"
      aria-labelledby={`knob-${item.key}`}
      className={cn(
        "inline-flex rounded-[9px] border border-border bg-bg p-[3px]",
        disabled && "opacity-50",
      )}
    >
      {(item.options ?? []).map((level) => {
        const on = item.value === level;
        return (
          <button
            key={level}
            role="radio"
            aria-checked={on}
            disabled={disabled}
            onClick={() => !on && onChange(level)}
            className={cn(
              "h-[30px] rounded-[7px] px-3 text-[13px] transition-colors disabled:cursor-not-allowed",
              on ? "bg-surface-2 text-fg shadow-sm" : "text-fg-muted hover:text-fg",
            )}
          >
            {LEVEL_LABEL[level] ?? level}
          </button>
        );
      })}
    </div>
  );
}

function NumberControl({ item, onChange }: { item: SettingItem; onChange: (v: number) => void }) {
  const value = Number(item.value);
  const min = item.min ?? 1;
  const max = item.max ?? 999;
  // A local draft only while typing (null otherwise), so the field always
  // shows the saved value when it isn't being edited.
  const [draft, setDraft] = useState<string | null>(null);

  const commit = (n: number) => {
    setDraft(null);
    if (!Number.isFinite(n)) return;
    const clamped = Math.min(max, Math.max(min, Math.round(n)));
    if (clamped !== value) onChange(clamped);
  };

  return (
    <div className="inline-flex items-center rounded-[9px] border border-border bg-bg p-[3px]">
      <StepButton label="Decrease" disabled={value <= min} onClick={() => commit(value - 1)}>
        <Minus className="size-3.5" />
      </StepButton>
      <input
        type="number"
        inputMode="numeric"
        min={min}
        max={max}
        value={draft ?? String(value)}
        aria-labelledby={`knob-${item.key}`}
        onChange={(e) => setDraft(e.target.value)}
        onBlur={() => (draft === null || draft.trim() === "" ? setDraft(null) : commit(Number(draft)))}
        onKeyDown={(e) => {
          if (e.key === "Enter") (e.target as HTMLInputElement).blur();
          if (e.key === "Escape") setDraft(null);
        }}
        className="h-[30px] w-14 bg-transparent text-center font-mono text-[14px] tabular-nums text-fg outline-none [appearance:textfield] [&::-webkit-inner-spin-button]:appearance-none [&::-webkit-outer-spin-button]:appearance-none"
      />
      <StepButton label="Increase" disabled={value >= max} onClick={() => commit(value + 1)}>
        <Plus className="size-3.5" />
      </StepButton>
    </div>
  );
}

function StepButton({
  label,
  disabled,
  onClick,
  children,
}: {
  label: string;
  disabled: boolean;
  onClick: () => void;
  children: ReactNode;
}) {
  return (
    <button
      aria-label={label}
      disabled={disabled}
      onClick={onClick}
      className="grid size-[30px] place-items-center rounded-[7px] text-fg-muted transition-colors hover:bg-surface-2 hover:text-fg disabled:opacity-40 disabled:hover:bg-transparent"
    >
      {children}
    </button>
  );
}

function contextLabel(window?: number | null): string {
  if (!window) return "";
  return window >= 1_000_000
    ? ` · ${+(window / 1_000_000).toFixed(1)}M context`
    : ` · ${Math.round(window / 1000)}k context`;
}

function ModelControl({
  item,
  models,
  loading,
  onChange,
}: {
  item: SettingItem;
  models: ModelOption[] | null;
  loading: boolean;
  onChange: (v: string) => void;
}) {
  const current = String(item.value ?? "");
  // Keep the current value selectable even if the proxy no longer lists it.
  const options: ModelOption[] = models
    ? models.some((m) => m.id === current)
      ? models
      : [{ id: current, context_window: null }, ...models]
    : [{ id: current, context_window: null }];

  return (
    <select
      value={current}
      disabled={!models || loading}
      aria-labelledby={`knob-${item.key}`}
      onChange={(e) => e.target.value !== current && onChange(e.target.value)}
      className="h-[38px] w-full min-w-0 rounded-[9px] border border-border bg-bg px-3 font-mono text-[13px] text-fg outline-none transition-colors hover:border-border-strong focus:border-ui-focus-border disabled:opacity-60 sm:w-72"
    >
      {options.map((m) => (
        <option key={m.id} value={m.id}>
          {m.id}
          {contextLabel(m.context_window)}
        </option>
      ))}
    </select>
  );
}
