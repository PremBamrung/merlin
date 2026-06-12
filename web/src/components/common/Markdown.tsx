import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { cn } from "@/lib/utils";

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
        "[&_h1]:mt-8 [&_h1]:mb-3 [&_h1]:text-[22px] [&_h1]:font-semibold [&_h1]:text-fg",
        "[&_h2]:mt-7 [&_h2]:mb-2 [&_h2]:text-[18px] [&_h2]:font-semibold [&_h2]:text-fg",
        "[&_h3]:mt-6 [&_h3]:mb-2 [&_h3]:text-[16px] [&_h3]:font-semibold [&_h3]:text-fg",
        "[&_p]:my-3 [&_ul]:my-3 [&_ol]:my-3 [&_li]:my-1",
        "[&_ul]:list-disc [&_ul]:pl-5 [&_ol]:list-decimal [&_ol]:pl-5",
        "[&_strong]:font-semibold [&_strong]:text-fg",
        "[&_a]:text-accent [&_a]:underline [&_a]:underline-offset-2 hover:[&_a]:text-accent-hover",
        "[&_blockquote]:border-l-2 [&_blockquote]:border-accent-border [&_blockquote]:pl-4 [&_blockquote]:text-fg-muted [&_blockquote]:italic",
        "[&_code]:rounded [&_code]:bg-surface-2 [&_code]:px-1.5 [&_code]:py-0.5 [&_code]:font-mono [&_code]:text-[13px]",
        "[&_pre]:my-4 [&_pre]:overflow-x-auto [&_pre]:rounded-[10px] [&_pre]:border [&_pre]:border-border [&_pre]:bg-surface [&_pre]:p-4",
        "[&_pre_code]:bg-transparent [&_pre_code]:p-0",
        "[&_hr]:my-6 [&_hr]:border-border",
        "[&_table]:my-4 [&_table]:w-full [&_th]:border-b [&_th]:border-border [&_th]:px-2 [&_th]:py-1 [&_th]:text-left [&_td]:border-b [&_td]:border-border [&_td]:px-2 [&_td]:py-1",
        className,
      )}
    >
      <ReactMarkdown remarkPlugins={[remarkGfm]}>{children}</ReactMarkdown>
    </div>
  );
}
