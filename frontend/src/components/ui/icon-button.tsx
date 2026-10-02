import type { ButtonHTMLAttributes } from "react";
import { cn } from "@/lib/utils";

export function IconButton({ label, className, children, ...props }: ButtonHTMLAttributes<HTMLButtonElement> & { label: string }) {
  return <button aria-label={label} title={label} className={cn("inline-flex size-10 shrink-0 items-center justify-center rounded-control border border-transparent hover:border-border hover:bg-hover-bg", className)} {...props}>{children}</button>;
}

