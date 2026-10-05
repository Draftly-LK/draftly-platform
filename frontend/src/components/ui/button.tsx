"use client";

import { LoaderCircle } from "lucide-react";
import type { ButtonHTMLAttributes } from "react";
import { cn } from "@/lib/utils";

export type ButtonVariant = "primary" | "secondary" | "ghost" | "destructive";
export type ButtonSize = "md" | "sm";

const variantClasses: Record<ButtonVariant, string> = {
  // Shared softly tinted primary action: navy label, amber boundary and icon.
  primary: [
    "primary-action border-primary-border bg-primary-bg font-semibold text-primary-ink transition-colors duration-150 hover:bg-primary-hover active:bg-primary-pressed motion-reduce:transition-none",
    "[&_svg]:size-4 [&_svg]:shrink-0 [&_svg]:text-primary-icon disabled:[&_svg]:text-disabled-fg",
  ].join(" "),
  secondary:
    "border-border-strong bg-surface text-ink hover:bg-hover-bg active:bg-active-bg aria-pressed:bg-selected-bg",
  ghost:
    "border-transparent bg-transparent text-ink hover:bg-hover-bg active:bg-active-bg aria-pressed:bg-selected-bg",
  destructive: "border-red bg-red text-white hover:border-red-hover hover:bg-red-hover active:brightness-95",
};

const baseClasses =
  "inline-flex cursor-pointer select-none items-center justify-center gap-2 rounded-control border text-sm font-medium disabled:cursor-not-allowed disabled:border-border disabled:bg-disabled-bg disabled:text-disabled-fg aria-busy:cursor-progress";

const sizeClasses: Record<ButtonSize, string> = {
  md: "min-h-10 px-4 py-2 [@media(pointer:coarse)]:min-h-11",
  sm: "min-h-8 px-3 py-1 [@media(pointer:coarse)]:min-h-11",
};

/** The button look for a link: `<Link className={buttonClass("primary")}>`. */
export function buttonClass(variant: ButtonVariant = "secondary", size: ButtonSize = "md"): string {
  // Every primary button is the same height, padding, font size and icon size, whatever `size` says.
  return cn(baseClasses, sizeClasses[variant === "primary" ? "md" : size], variantClasses[variant]);
}

/**
 * `loading` keeps the label and swaps the icon slot for a spinner. The button
 * stays enabled in the DOM (so focus is not lost mid-request) but ignores
 * clicks, and announces itself as busy.
 */
export function Button({
  className,
  variant = "secondary",
  size = "md",
  loading = false,
  onClick,
  children,
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: ButtonVariant;
  size?: ButtonSize;
  loading?: boolean;
}) {
  return (
    <button
      aria-busy={loading || undefined}
      onClick={loading ? (event) => event.preventDefault() : onClick}
      className={cn(buttonClass(variant, size), className)}
      {...props}
    >
      {loading ? <LoaderCircle aria-hidden="true" className="size-4 animate-spin" strokeWidth={1.5} /> : null}
      {children}
    </button>
  );
}
