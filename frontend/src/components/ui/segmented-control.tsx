"use client";

import { cn } from "@/lib/utils";

/** The rounded track that holds the options. */
export const segmentedTrack = "border-border-strong bg-canvas inline-flex max-w-full rounded-control border p-0.5";

/** One option: small on phones, the selected one raised on a white segment. */
export function segmentedOption(selected: boolean) {
  return cn(
    "rounded-control inline-flex flex-auto cursor-pointer items-center justify-center gap-1.5 whitespace-nowrap border px-2.5 text-xs leading-none transition-colors duration-150 disabled:cursor-not-allowed disabled:opacity-60 motion-reduce:transition-none h-7 sm:h-8 sm:px-3.5 sm:text-sm",
    selected
      ? "border-border-strong bg-surface text-forest font-semibold"
      : "text-muted-ink hover:text-ink border-transparent font-medium",
  );
}

export interface SegmentedOption<T extends string> {
  value: T;
  label: string;
  /** Shown instead of `label` on phones when the full label would not fit. */
  shortLabel?: string;
}

/**
 * A compact choice between a few views or scopes: one rounded track, the
 * selected option raised on a white segment. Each option is a pressed/unpressed
 * button, so screen readers announce the current choice.
 */
export function SegmentedControl<T extends string>({
  options,
  value,
  onChange,
  label,
  labelledBy,
  disabled = false,
  className,
}: {
  options: ReadonlyArray<SegmentedOption<T>>;
  value: T;
  onChange: (next: T) => void;
  /** Accessible name of the group, when no visible heading names it. */
  label?: string;
  labelledBy?: string;
  disabled?: boolean;
  className?: string;
}) {
  return (
    <div
      role="group"
      aria-label={labelledBy ? undefined : label}
      aria-labelledby={labelledBy}
      className={cn(segmentedTrack, className)}
    >
      {options.map((option) => {
        const selected = option.value === value;
        return (
          <button
            key={option.value}
            type="button"
            aria-pressed={selected}
            aria-label={option.shortLabel ? option.label : undefined}
            disabled={disabled}
            onClick={() => onChange(option.value)}
            className={segmentedOption(selected)}
          >
            {option.shortLabel ? (
              <>
                <span aria-hidden="true" className="sm:hidden">{option.shortLabel}</span>
                <span aria-hidden="true" className="hidden sm:inline">{option.label}</span>
              </>
            ) : (
              option.label
            )}
          </button>
        );
      })}
    </div>
  );
}
