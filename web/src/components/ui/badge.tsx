import * as React from "react";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/lib/utils";

const badgeVariants = cva(
  "inline-flex items-center gap-1 rounded-[6px] px-2 py-0.5 text-[12px] font-medium leading-tight transition-colors",
  {
    variants: {
      variant: {
        default: "bg-surface-2 text-fg-muted border border-border",
        accent: "bg-accent-subtle text-accent-lit border border-accent-border",
        outline: "border border-border text-fg-subtle",
      },
    },
    defaultVariants: { variant: "default" },
  },
);

export interface BadgeProps
  extends React.HTMLAttributes<HTMLSpanElement>,
    VariantProps<typeof badgeVariants> {}

export function Badge({ className, variant, ...props }: BadgeProps) {
  return (
    <span className={cn(badgeVariants({ variant }), className)} {...props} />
  );
}
