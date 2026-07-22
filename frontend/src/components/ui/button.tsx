import type { ButtonHTMLAttributes } from "react";
import { cn } from "@/lib/utils";

type ButtonVariant = "primary" | "secondary" | "ghost" | "danger";

export function Button({ className, variant = "secondary", ...props }: ButtonHTMLAttributes<HTMLButtonElement> & { variant?: ButtonVariant }) {
  return <button className={cn("inline-flex min-h-10 items-center justify-center gap-2 rounded border px-3 py-2 font-medium disabled:cursor-not-allowed disabled:border-border disabled:bg-disabled-bg disabled:text-disabled-fg", variant === "primary" && "border-forest bg-forest text-white hover:bg-[#1c4431]", variant === "secondary" && "border-border-strong bg-surface hover:bg-hover-bg", variant === "ghost" && "border-transparent bg-transparent hover:bg-hover-bg", variant === "danger" && "border-red bg-red text-white", className)} {...props} />;
}

