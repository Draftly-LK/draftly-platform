import type { ButtonHTMLAttributes } from "react";
import { cn } from "@/lib/utils";

type ButtonVariant = "primary" | "secondary" | "ghost" | "danger";

export function Button({
  className,
  variant = "secondary",
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & { variant?: ButtonVariant }) {
  return (
    <button
      className={cn(
        "disabled:border-border disabled:bg-disabled-bg disabled:text-disabled-fg inline-flex min-h-10 items-center justify-center gap-2 rounded border px-3 py-2 font-medium disabled:cursor-not-allowed",
        variant === "primary" &&
          "border-forest bg-forest text-white hover:brightness-90",
        variant === "secondary" &&
          "border-border-strong bg-surface hover:bg-hover-bg",
        variant === "ghost" &&
          "hover:bg-hover-bg border-transparent bg-transparent",
        variant === "danger" && "border-red bg-red text-white",
        className,
      )}
      {...props}
    />
  );
}
