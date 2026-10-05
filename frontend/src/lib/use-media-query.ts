"use client";

import { useSyncExternalStore } from "react";

/**
 * Whether a CSS media query matches. `null` on the server and during hydration,
 * so markup never claims a layout it cannot know; the real answer arrives on
 * the first client render after.
 */
export function useMediaQuery(query: string): boolean | null {
  return useSyncExternalStore(
    (notify) => {
      const list = window.matchMedia(query);
      list.addEventListener("change", notify);
      return () => list.removeEventListener("change", notify);
    },
    () => window.matchMedia(query).matches,
    () => null,
  );
}
