"use client";

import {
  AlertCircle,
  Check,
  CircleDashed,
  FileWarning,
  LoaderCircle,
  Pencil,
  ShieldAlert,
  TriangleAlert,
} from "lucide-react";
import { useLocale } from "next-intl";
import {
  checkLabels,
  processingLabels,
  stepLabels,
  verificationLabels,
} from "@/lib/i18n/labels";
import type {
  CheckStatus,
  ProcessingState,
  StepState,
  VerificationState,
} from "@/types";
import { cn } from "@/lib/utils";

type Status = VerificationState | ProcessingState | CheckStatus | StepState;

const styles: Record<Status, string> = {
  unreviewed: "border-border-strong bg-surface text-ink",
  verified: "border-forest bg-soft-green text-forest",
  corrected: "border-teal bg-teal-bg text-teal",
  conflict: "border-amber bg-amber-bg text-amber-text",
  blocked: "border-red bg-red-bg text-red",
  uploaded: "border-border-strong bg-surface text-ink",
  extracting: "border-teal bg-teal-bg text-teal",
  "ready-for-review": "border-forest bg-soft-green text-forest",
  failed: "border-red bg-red-bg text-red",
  replaced: "border-border-strong bg-disabled-bg text-ink",
  pass: "border-forest bg-soft-green text-forest",
  warning: "border-amber bg-amber-bg text-amber-text",
  fail: "border-red bg-red-bg text-red",
  "needs-review": "border-teal bg-teal-bg text-teal",
  "not-started": "border-border-strong bg-surface text-muted-ink",
  "in-progress": "border-teal bg-teal-bg text-teal",
  complete: "border-forest bg-soft-green text-forest",
};

function details(status: Status, locale: "en" | "si") {
  if (status in verificationLabels)
    return {
      label: verificationLabels[status as VerificationState][locale],
      icon:
        status === "verified"
          ? Check
          : status === "corrected"
            ? Pencil
            : status === "conflict"
              ? TriangleAlert
              : status === "blocked"
                ? ShieldAlert
                : CircleDashed,
    };
  if (status in processingLabels)
    return {
      label: processingLabels[status as ProcessingState][locale],
      icon:
        status === "ready-for-review"
          ? Check
          : status === "extracting"
            ? LoaderCircle
            : status === "failed"
              ? FileWarning
              : CircleDashed,
    };
  if (status in checkLabels)
    return {
      label: checkLabels[status as CheckStatus][locale],
      icon:
        status === "pass"
          ? Check
          : status === "warning"
            ? TriangleAlert
            : status === "fail"
              ? ShieldAlert
              : AlertCircle,
    };
  return {
    label: stepLabels[status as StepState][locale],
    icon:
      status === "complete"
        ? Check
        : status === "blocked"
          ? ShieldAlert
          : CircleDashed,
  };
}

export function StatusBadge({
  status,
  className,
}: {
  status: Status;
  className?: string;
}) {
  const locale = useLocale() === "si" ? "si" : "en";
  const { label, icon: Icon } = details(status, locale);
  return (
    <span
      className={cn(
        "inline-flex min-h-7 items-center gap-1.5 rounded-full border px-2 py-1 text-xs font-semibold",
        styles[status],
        className,
      )}
    >
      <Icon aria-hidden="true" className="size-4" strokeWidth={1.5} />
      {label}
    </span>
  );
}
