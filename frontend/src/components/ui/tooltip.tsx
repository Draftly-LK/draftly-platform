"use client";

import { useCallback, useEffect, useRef, useState, type ReactNode } from "react";
import { createPortal } from "react-dom";

/**
 * A small label that appears beside its trigger on hover and on keyboard focus,
 * drawn in a portal so a clipping ancestor (the sidebar, a scroll area) cannot
 * cut it off. It is supplementary: the trigger keeps its own accessible name, so
 * the tooltip is hidden from assistive technology. Escape dismisses it.
 */
export function Tooltip({
  label,
  shortcut,
  enabled = () => true,
  children,
}: {
  label: string;
  /** Shown beside the label, e.g. "Ctrl+\". */
  shortcut?: string;
  /** Checked each time the tooltip would show, e.g. only while the sidebar is a rail. */
  enabled?: () => boolean;
  children: ReactNode;
}) {
  const anchorRef = useRef<HTMLSpanElement>(null);
  const timer = useRef<number | undefined>(undefined);
  const [pos, setPos] = useState<{ left: number; top: number } | null>(null);

  const hide = useCallback(() => {
    window.clearTimeout(timer.current);
    setPos(null);
  }, []);

  const show = useCallback(
    (delay: number) => {
      window.clearTimeout(timer.current);
      timer.current = window.setTimeout(() => {
        const rect = anchorRef.current?.getBoundingClientRect();
        if (!rect || !enabled()) return;
        setPos({ left: rect.right + 8, top: rect.top + rect.height / 2 });
      }, delay);
    },
    [enabled],
  );

  useEffect(() => {
    if (!pos) return;
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") hide();
    };
    document.addEventListener("keydown", onKeyDown);
    return () => document.removeEventListener("keydown", onKeyDown);
  }, [hide, pos]);

  useEffect(() => () => window.clearTimeout(timer.current), []);

  // A click (or tap) acts on the trigger, so the hint has done its job. Attached here, not as a
  // JSX handler, because the wrapper is not itself interactive.
  useEffect(() => {
    const anchor = anchorRef.current;
    anchor?.addEventListener("click", hide);
    return () => anchor?.removeEventListener("click", hide);
  }, [hide]);

  return (
    <span
      ref={anchorRef}
      className="block"
      onMouseEnter={() => show(250)}
      onMouseLeave={hide}
      onFocus={() => show(0)}
      onBlur={hide}
    >
      {children}
      {pos
        ? createPortal(
            <span
              aria-hidden="true"
              data-tooltip
              style={{ left: pos.left, top: pos.top }}
              className="pointer-events-none fixed z-50 flex -translate-y-1/2 items-center gap-2 whitespace-nowrap rounded border border-white/10 bg-surface-inverse px-2.5 py-1.5 text-xs font-medium text-white shadow-popover"
            >
              {label}
              {shortcut ? (
                <kbd className="rounded border border-white/20 px-1 font-sans text-xs text-on-dark-muted">{shortcut}</kbd>
              ) : null}
            </span>,
            document.body,
          )
        : null}
    </span>
  );
}
