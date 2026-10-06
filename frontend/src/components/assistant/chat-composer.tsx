"use client";

import { LoaderCircle, Send } from "lucide-react";
import { useLayoutEffect, useRef } from "react";
import { buttonClass } from "@/components/ui/button";
import { cn } from "@/lib/utils";

/** About eight lines; a longer question scrolls inside the box. */
const MAX_HEIGHT_PX = 200;

/**
 * The question bar shared by Research and the matter assistant: one line,
 * fully rounded, growing upward with the text. Enter sends and Shift+Enter
 * adds a line; an input method still composing (Sinhala) keeps its Enter.
 */
export function ChatComposer({
  id,
  label,
  placeholder,
  value,
  onChange,
  onSubmit,
  sendLabel,
  busyLabel,
  busy = false,
  disabled = false,
  className,
}: {
  id: string;
  label: string;
  placeholder: string;
  value: string;
  onChange: (value: string) => void;
  onSubmit: () => void;
  sendLabel: string;
  busyLabel: string;
  busy?: boolean;
  disabled?: boolean;
  className?: string;
}) {
  const ref = useRef<HTMLTextAreaElement>(null);
  const canSend = !busy && !disabled && value.trim().length > 0;

  // Fit the box to its text: one line when short, up to MAX_HEIGHT_PX, then scroll.
  useLayoutEffect(() => {
    const field = ref.current;
    if (!field) return;
    field.style.height = "auto";
    field.style.height = `${Math.min(field.scrollHeight, MAX_HEIGHT_PX)}px`;
    field.style.overflowY = field.scrollHeight > MAX_HEIGHT_PX ? "auto" : "hidden";
  }, [value]);

  return (
    <form
      className={cn(
        "border-border-control bg-surface shadow-popover focus-within:border-forest focus-within:ring-border-active flex items-end gap-2 rounded-[32px] border py-1.5 pl-5 pr-1.5 focus-within:ring-4",
        className,
      )}
      onSubmit={(event) => {
        event.preventDefault();
        if (canSend) onSubmit();
      }}
    >
      <label className="sr-only" htmlFor={id}>
        {label}
      </label>
      <textarea
        ref={ref}
        id={id}
        rows={1}
        className="min-w-0 flex-1 resize-none bg-transparent py-2 leading-6 outline-none focus-visible:outline-none"
        placeholder={placeholder}
        value={value}
        disabled={disabled}
        onChange={(event) => onChange(event.target.value)}
        onKeyDown={(event) => {
          if (event.key === "Enter" && !event.shiftKey && !event.nativeEvent.isComposing) {
            event.preventDefault();
            if (canSend) onSubmit();
          }
        }}
      />
      <button
        type="submit"
        aria-label={busy ? busyLabel : sendLabel}
        title={busy ? busyLabel : sendLabel}
        aria-busy={busy || undefined}
        disabled={!canSend}
        className={cn(
          buttonClass("primary"),
          "size-10 min-h-10 shrink-0 rounded-full p-0 [@media(pointer:coarse)]:size-11",
        )}
      >
        {busy ? (
          <LoaderCircle aria-hidden="true" className="animate-spin" strokeWidth={1.5} />
        ) : (
          <Send aria-hidden="true" strokeWidth={1.5} />
        )}
      </button>
      <span className="sr-only" role="status">
        {busy ? busyLabel : ""}
      </span>
    </form>
  );
}
