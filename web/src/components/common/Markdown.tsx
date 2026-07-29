import { isValidElement, type ReactNode } from "react";
import ReactMarkdown, { type Components } from "react-markdown";
import remarkGfm from "remark-gfm";
import { CopyButton } from "@/components/common/CopyButton";
import { cn } from "@/lib/utils";

// Inline citation chips: `linkifyCitationMarkers` rewrites answer markers into
// `[n](#cite-<messageId>-<item_id>)`; here we render that sentinel href as a
// small superscript pill that scrolls to (and briefly flashes) the matching
// Source card rendered below the answer — keeping the reader in the conversation
// instead of navigating away.
const CITE_PREFIX = "#cite-";

/** Scroll a Source card into view and replay its highlight animation. */
function flashCitation(anchorId: string): void {
  const el = document.getElementById(anchorId);
  if (!el) return;
  el.scrollIntoView({ behavior: "smooth", block: "center" });
  el.classList.remove("cite-flash");
  void el.offsetWidth; // force reflow so the animation restarts on repeat clicks
  el.classList.add("cite-flash");
}

/** Flatten a markdown node's children into plain text (for the copy button). */
function nodeText(node: ReactNode): string {
  if (node == null || typeof node === "boolean") return "";
  if (typeof node === "string" || typeof node === "number") return String(node);
  if (Array.isArray(node)) return node.map(nodeText).join("");
  if (isValidElement(node)) {
    return nodeText((node.props as { children?: ReactNode }).children);
  }
  return "";
}

/** A fenced code block with a language label and a hover copy button. */
function CodeBlock({ children }: { children?: ReactNode }) {
  const codeEl = isValidElement(children) ? children : null;
  const className =
    (codeEl?.props as { className?: string } | undefined)?.className ?? "";
  const lang = /language-(\w+)/.exec(className)?.[1] ?? "";
  const code = nodeText(children).replace(/\n$/, "");

  return (
    <div className="group/code relative my-4 overflow-hidden rounded-[10px] border border-border bg-surface">
      <div className="flex items-center justify-between border-b border-border bg-surface-2/50 px-3 py-1.5">
        <span className="font-mono text-[11px] uppercase tracking-wide text-fg-subtle">
          {lang || "code"}
        </span>
        <CopyButton
          text={code}
          size="icon-sm"
          className="-my-1 size-7 opacity-0 transition-opacity group-hover/code:opacity-100"
        />
      </div>
      <pre className="overflow-x-auto p-4">{children}</pre>
    </div>
  );
}

const components: Components = {
  a({ href, children, title }) {
    if (href?.startsWith(CITE_PREFIX)) {
      return (
        <a
          href={href}
          onClick={(e) => {
            e.preventDefault();
            flashCitation(href.slice(1));
          }}
          className="ml-0.5 inline-block cursor-pointer rounded bg-accent-subtle px-1 align-super text-[10px] font-medium leading-none text-accent-lit !no-underline hover:bg-accent-border"
        >
          {children}
        </a>
      );
    }
    return (
      <a href={href} title={title} target="_blank" rel="noreferrer">
        {children}
      </a>
    );
  },
  // Fenced blocks render through `pre`; inline `code` keeps the default styling.
  pre({ children }) {
    return <CodeBlock>{children}</CodeBlock>;
  },
};

/**
 * Markdown renderer with prose styling tuned to the design tokens.
 * Reading column is capped to ~70ch by the caller (Reader); we just style runs.
 */
export function Markdown({
  children,
  className,
}: {
  children: string;
  className?: string;
}) {
  return (
    <div
      className={cn(
        "max-w-none text-[16px] leading-[26px] text-fg/90",
        "[&_h1]:mt-8 [&_h1]:mb-3 [&_h1]:font-display [&_h1]:text-[22px] [&_h1]:font-semibold [&_h1]:text-fg",
        "[&_h2]:mt-7 [&_h2]:mb-2 [&_h2]:font-display [&_h2]:text-[18px] [&_h2]:font-semibold [&_h2]:text-fg",
        "[&_h3]:mt-6 [&_h3]:mb-2 [&_h3]:font-display [&_h3]:text-[16px] [&_h3]:font-semibold [&_h3]:text-fg",
        "[&_p]:my-3 [&_ul]:my-3 [&_ol]:my-3 [&_li]:my-1",
        "[&_ul]:list-disc [&_ul]:pl-5 [&_ol]:list-decimal [&_ol]:pl-5",
        "[&_strong]:font-semibold [&_strong]:text-fg",
        "[&_a]:text-accent-lit [&_a]:underline [&_a]:underline-offset-2 hover:[&_a]:text-fg",
        "[&_blockquote]:border-l-2 [&_blockquote]:border-accent-border [&_blockquote]:pl-4 [&_blockquote]:text-fg-muted [&_blockquote]:italic",
        "[&_code]:rounded [&_code]:bg-surface-2 [&_code]:px-1.5 [&_code]:py-0.5 [&_code]:font-mono [&_code]:text-[13px]",
        // Fenced blocks own their chrome (see `CodeBlock`); only the inner `pre`
        // needs horizontal scroll + a transparent `code` child.
        "[&_pre_code]:bg-transparent [&_pre_code]:p-0 [&_pre_code]:text-[13px]",
        "[&_hr]:my-6 [&_hr]:border-border",
        "[&_table]:my-4 [&_table]:w-full [&_th]:border-b [&_th]:border-border [&_th]:px-2 [&_th]:py-1 [&_th]:text-left [&_td]:border-b [&_td]:border-border [&_td]:px-2 [&_td]:py-1",
        className,
      )}
    >
      <ReactMarkdown remarkPlugins={[remarkGfm]} components={components}>
        {children}
      </ReactMarkdown>
    </div>
  );
}
