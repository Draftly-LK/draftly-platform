"use client";

import { useTranslations } from "next-intl";
import { usePathname } from "next/navigation";
import { useEffect, useRef, useState } from "react";

/** Navigations quicker than this finish before anything is drawn, so fast
 *  page changes do not flicker. */
const SHOW_AFTER_MS = 150;
/** Safety net: a navigation that never lands (blocked, errored) still clears. */
const GIVE_UP_AFTER_MS = 15_000;

type Phase = "idle" | "pending" | "running" | "done";

/**
 * A slim gold bar and spinner at the top of the window while a clicked link is
 * loading the next page. It starts on a same-origin link click and finishes
 * when the pathname changes, so it only appears when a page change is actually
 * in flight.
 */
export function NavigationProgress() {
  const t = useTranslations("app");
  const pathname = usePathname();
  const [phase, setPhase] = useState<Phase>("idle");
  const timers = useRef<number[]>([]);

  function clearTimers() {
    for (const id of timers.current) window.clearTimeout(id);
    timers.current = [];
  }

  useEffect(() => {
    function onClick(event: MouseEvent) {
      if (
        event.defaultPrevented ||
        event.button !== 0 ||
        event.metaKey ||
        event.ctrlKey ||
        event.shiftKey ||
        event.altKey
      ) {
        return;
      }
      const anchor = (event.target as Element | null)?.closest("a");
      if (!anchor || anchor.target === "_blank" || anchor.hasAttribute("download")) return;
      const url = new URL(anchor.href, window.location.href);
      if (url.origin !== window.location.origin) return;
      // Same path (only ?query or #hash changes): these are instant, and the
      // bar finishes on a pathname change, so it would never clear.
      if (url.pathname === window.location.pathname) return;

      clearTimers();
      setPhase("pending");
      timers.current.push(
        window.setTimeout(() => setPhase((p) => (p === "pending" ? "running" : p)), SHOW_AFTER_MS),
        window.setTimeout(() => setPhase("done"), GIVE_UP_AFTER_MS),
      );
    }
    document.addEventListener("click", onClick, true);
    return () => document.removeEventListener("click", onClick, true);
  }, []);

  // The new page has rendered: finish the bar, then fade it out.
  useEffect(() => {
    clearTimers();
    setPhase((p) => (p === "running" ? "done" : "idle"));
  }, [pathname]);

  useEffect(() => {
    if (phase !== "done") return;
    const id = window.setTimeout(() => setPhase("idle"), 350);
    return () => window.clearTimeout(id);
  }, [phase]);

  useEffect(() => clearTimers, []);

  if (phase === "idle" || phase === "pending") return null;
  const done = phase === "done";

  return (
    <div
      role="progressbar"
      aria-label={t("navigating")}
      aria-busy={!done}
      data-no-print
      className={`pointer-events-none fixed inset-x-0 top-0 z-50 transition-opacity duration-300 ${done ? "opacity-0" : "opacity-100"}`}
    >
      <div
        className={`bg-gold h-[3px] ${
          done
            ? "w-full transition-[width] duration-200 ease-out"
            : "animate-nav-progress w-[90%]"
        }`}
      />
      <span
        aria-hidden="true"
        className="border-gold-soft border-t-gold absolute right-3 top-2 size-4 animate-spin rounded-full border-2"
      />
    </div>
  );
}
