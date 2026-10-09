import { CircleAlert, Info, TriangleAlert, type LucideIcon } from "lucide-react";
import type { ReactNode } from "react";
import { cn } from "@/lib/utils";

type AlertTone = "danger" | "warning" | "info";

const tones: Record<AlertTone, { box: string; icon: LucideIcon; role: "alert" | "status" }> = {
  danger: { box: "border-red bg-red-bg text-red", icon: CircleAlert, role: "alert" },
  warning: { box: "border-amber bg-amber-bg text-amber-text", icon: TriangleAlert, role: "status" },
  info: { box: "border-teal bg-teal-bg text-teal", icon: Info, role: "status" },
};

/** A message inside a page: an icon, the words, and (for errors) what to do next. Never colour alone. */
export function InlineAlert({
  tone = "danger",
  children,
  className,
}: {
  tone?: AlertTone;
  children: ReactNode;
  className?: string;
}) {
  if (tone === "warning") return null;
  const { box, icon: Icon, role } = tones[tone];
  return (
    <div role={role} className={cn("flex items-start gap-2 rounded border-l-2 p-3 text-sm", box, className)}>
      <Icon aria-hidden="true" className="mt-0.5 size-4 shrink-0" strokeWidth={1.5} />
      <div className="min-w-0">{children}</div>
    </div>
  );
}
