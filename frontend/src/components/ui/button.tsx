import type { ButtonHTMLAttributes } from "react";
import { cn } from "@/lib/utils";

type ButtonVariant = "primary" | "secondary" | "ghost" | "danger" | "accent";

export function Button({
  className,
  variant = "secondary",
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & { variant?: ButtonVariant }) {
  return (
    <button
      className={cn(
        "disabled:border-border disabled:bg-disabled-bg disabled:text-disabled-fg inline-flex min-h-10 cursor-pointer items-center justify-center gap-2 rounded border px-3.5 py-2 font-medium disabled:cursor-not-allowed disabled:shadow-none",
        variant === "primary" &&
          "border-forest bg-forest shadow-card text-white hover:bg-navy-800",
        variant === "secondary" &&
          "border-border-strong bg-surface shadow-card hover:bg-hover-bg",
        variant === "accent" &&
          "border-gold bg-gold text-navy-950 shadow-card font-semibold hover:brightness-105",
        variant === "ghost" &&
          "hover:bg-hover-bg border-transparent bg-transparent",
        variant === "danger" && "border-red bg-red text-white",
        className,
      )}
      {...props}
    />
  );
}
