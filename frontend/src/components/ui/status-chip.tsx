import type { LucideIcon } from "lucide-react";
import type { ReactNode } from "react";
import { cn } from "@/lib/utils";

export type StatusTone = "neutral" | "success" | "warning" | "danger" | "info";

/** Border, fill and text per tone. Every pair is at least 4.5:1 for the text. */
export const statusToneClasses: Record<StatusTone, string> = {
  neutral: "border-border-strong bg-surface text-ink",
  success: "border-success bg-success-bg text-success",
  warning: "border-amber bg-amber-bg text-amber-text",
  danger: "border-red bg-red-bg text-red",
  info: "border-teal bg-teal-bg text-teal",
};

/**
 * A short status label. The icon and the text are both required, so colour is
 * never the only carrier of meaning.
 */
export function StatusChip({
  tone = "neutral",
  icon: Icon,
  children,
  className,
  ...props
}: {
  tone?: StatusTone;
  icon: LucideIcon;
  children: ReactNode;
  className?: string;
} & Omit<React.HTMLAttributes<HTMLSpanElement>, "children">) {
  return (
    <span
      className={cn(
        "inline-flex min-h-7 items-center gap-1.5 rounded-full border px-2 py-1 text-xs font-semibold",
        statusToneClasses[tone],
        className,
      )}
      {...props}
    >
      <Icon aria-hidden="true" className="size-4" strokeWidth={1.5} />
      {children}
    </span>
  );
}
