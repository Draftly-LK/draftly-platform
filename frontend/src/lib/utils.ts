import { clsx, type ClassValue } from "clsx";
import { extendTailwindMerge } from "tailwind-merge";

// Teach tailwind-merge the custom radius tokens in tailwind.config.ts, so a
// caller's `rounded-*` override replaces `rounded-control` instead of stacking.
const twMerge = extendTailwindMerge({
  extend: {
    theme: { borderRadius: ["control", "card", "dialog"] },
    // `text-compact` is a font size (13px); without this it is mistaken for a text colour.
    classGroups: {
      "font-size": [{ text: ["compact"] }],
    },
  },
});

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}
