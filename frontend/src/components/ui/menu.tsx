"use client";

import type { LucideIcon } from "lucide-react";
import Link from "next/link";
import { useCallback, useEffect, useId, useRef, useState, type ReactNode } from "react";
import { cn } from "@/lib/utils";

export interface MenuItem {
  key: string;
  label: ReactNode;
  /** Pass this only from a client component: a server component cannot hand a component function across the boundary. */
  icon?: LucideIcon;
  /** Navigates. Without it the item is a button and runs `onSelect`. */
  href?: string;
  onSelect?: () => void;
  tone?: "default" | "danger";
}

/**
 * A button that opens a short list of actions. Keyboard: Enter / Space / ArrowDown
 * open it and focus the first item; Arrow keys, Home and End move; Escape closes
 * and returns focus to the button; Tab or a click outside closes it.
 */
export function Menu({
  label,
  trigger,
  items,
  align = "left",
  side = "bottom",
  triggerClassName,
  rootClassName,
}: {
  /** Accessible name of the trigger button. */
  label: string;
  trigger: ReactNode;
  items: MenuItem[];
  align?: "left" | "right";
  side?: "bottom" | "top";
  triggerClassName?: string;
  rootClassName?: string;
}) {
  const [open, setOpen] = useState(false);
  const rootRef = useRef<HTMLDivElement>(null);
  const triggerRef = useRef<HTMLButtonElement>(null);
  const listId = useId();

  const itemElements = useCallback(
    () => Array.from(rootRef.current?.querySelectorAll<HTMLElement>("[role='menuitem']") ?? []),
    [],
  );

  const close = useCallback((returnFocus: boolean) => {
    setOpen(false);
    if (returnFocus) triggerRef.current?.focus();
  }, []);

  useEffect(() => {
    if (!open) return;
    itemElements()[0]?.focus();
    const onPointerDown = (event: PointerEvent) => {
      if (!rootRef.current?.contains(event.target as Node)) setOpen(false);
    };
    document.addEventListener("pointerdown", onPointerDown);
    return () => document.removeEventListener("pointerdown", onPointerDown);
  }, [open, itemElements]);

  const onListKeyDown = (event: React.KeyboardEvent) => {
    const elements = itemElements();
    const index = elements.indexOf(document.activeElement as HTMLElement);
    const move = (next: number) => {
      event.preventDefault();
      elements[(next + elements.length) % elements.length]?.focus();
    };
    if (event.key === "ArrowDown") move(index + 1);
    else if (event.key === "ArrowUp") move(index - 1);
    else if (event.key === "Home") move(0);
    else if (event.key === "End") move(elements.length - 1);
    else if (event.key === "Escape") {
      event.preventDefault();
      close(true);
    } else if (event.key === "Tab") close(false);
  };

  const itemClass = (tone: MenuItem["tone"]) =>
    cn(
      "flex min-h-10 w-full cursor-pointer items-center gap-2 rounded-control px-3 text-left text-sm hover:bg-hover-bg focus-visible:bg-hover-bg",
      tone === "danger" ? "text-red" : "text-ink",
    );

  return (
    <div ref={rootRef} className={cn("relative", rootClassName)}>
      <button
        ref={triggerRef}
        type="button"
        aria-label={label}
        aria-haspopup="menu"
        aria-expanded={open}
        aria-controls={open ? listId : undefined}
        onClick={() => setOpen((value) => !value)}
        onKeyDown={(event) => {
          if (event.key === "ArrowDown" && !open) {
            event.preventDefault();
            setOpen(true);
          }
        }}
        className={triggerClassName}
      >
        {trigger}
      </button>
      {open ? (
        <div
          id={listId}
          role="menu"
          tabIndex={-1}
          aria-label={label}
          onKeyDown={onListKeyDown}
          className={cn(
            "absolute z-30 min-w-48 rounded border border-border bg-surface p-1 shadow-popover",
            align === "right" ? "right-0" : "left-0",
            side === "top" ? "bottom-full mb-1" : "top-full mt-1",
          )}
        >
          {items.map(({ key, label: itemLabel, icon: Icon, href, onSelect, tone }) => {
            const content = (
              <>
                {Icon ? <Icon aria-hidden="true" className="size-4 shrink-0" strokeWidth={1.5} /> : null}
                {itemLabel}
              </>
            );
            return href ? (
              <Link key={key} href={href} role="menuitem" className={itemClass(tone)} onClick={() => close(false)}>
                {content}
              </Link>
            ) : (
              <button
                key={key}
                type="button"
                role="menuitem"
                className={itemClass(tone)}
                onClick={() => {
                  close(true);
                  onSelect?.();
                }}
              >
                {content}
              </button>
            );
          })}
        </div>
      ) : null}
    </div>
  );
}
