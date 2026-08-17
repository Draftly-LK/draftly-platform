"use client";

import {
  AlertCircle,
  Archive,
  Check,
  CircleCheck,
  CircleDashed,
  FileWarning,
  Inbox,
  LoaderCircle,
  Lock,
  Pencil,
  ScanEye,
  ShieldAlert,
  ShieldCheck,
  TriangleAlert,
  Upload,
} from "lucide-react";
import { useLocale } from "next-intl";
import {
  checkLabels,
  physicalOriginalLabels,
  sourceFileStateLabels,
  stepLabels,
  verificationLabels,
} from "@/lib/i18n/labels";
import type {
  CheckStatus,
  PhysicalOriginalStatus,
  SourceFileState,
  StepState,
  VerificationState,
} from "@/types";
import { cn } from "@/lib/utils";

type Status =
  | VerificationState
  | SourceFileState
  | PhysicalOriginalStatus
  | CheckStatus
  | StepState;

const styles: Record<Status, string> = {
  unreviewed: "border-border-strong bg-surface text-ink",
  verified: "border-forest bg-soft-green text-forest",
  corrected: "border-teal bg-teal-bg text-teal",
  conflict: "border-amber bg-amber-bg text-amber-text",
  blocked: "border-red bg-red-bg text-red",
  UPLOAD_INITIATED: "border-border-strong bg-surface text-ink",
  QUARANTINED: "border-amber bg-amber-bg text-amber-text",
  VALIDATED: "border-border-strong bg-surface text-ink",
  STORED: "border-border-strong bg-surface text-ink",
  PROCESSING: "border-teal bg-teal-bg text-teal",
  PROCESSED: "border-forest bg-soft-green text-forest",
  PROCESSING_FAILED: "border-red bg-red-bg text-red",
  REJECTED: "border-red bg-red-bg text-red",
  SUPERSEDED: "border-border-strong bg-disabled-bg text-ink",
  NOT_REQUIRED: "border-border-strong bg-surface text-muted-ink",
  UNKNOWN: "border-border-strong bg-surface text-ink",
  COPY_ONLY: "border-amber bg-amber-bg text-amber-text",
  ORIGINAL_REPORTED: "border-teal bg-teal-bg text-teal",
  ORIGINAL_INSPECTED: "border-forest bg-soft-green text-forest",
  pass: "border-forest bg-soft-green text-forest",
  warning: "border-amber bg-amber-bg text-amber-text",
  fail: "border-red bg-red-bg text-red",
  "needs-review": "border-teal bg-teal-bg text-teal",
  "not-started": "border-border-strong bg-surface text-muted-ink",
  "in-progress": "border-teal bg-teal-bg text-teal",
  complete: "border-forest bg-soft-green text-forest",
};

/** Every badge is icon + text; colour alone never carries the status. */
const sourceFileIcons: Record<SourceFileState, typeof Check> = {
  UPLOAD_INITIATED: Upload,
  QUARANTINED: Lock,
  VALIDATED: ShieldCheck,
  STORED: Inbox,
  PROCESSING: LoaderCircle,
  PROCESSED: Check,
  PROCESSING_FAILED: FileWarning,
  REJECTED: ShieldAlert,
  SUPERSEDED: Archive,
};

const physicalOriginalIcons: Record<PhysicalOriginalStatus, typeof Check> = {
  NOT_REQUIRED: CircleDashed,
  UNKNOWN: AlertCircle,
  COPY_ONLY: FileWarning,
  ORIGINAL_REPORTED: ScanEye,
  ORIGINAL_INSPECTED: CircleCheck,
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
  if (status in sourceFileStateLabels)
    return {
      label: sourceFileStateLabels[status as SourceFileState][locale],
      icon: sourceFileIcons[status as SourceFileState],
    };
  if (status in physicalOriginalLabels)
    return {
      label: physicalOriginalLabels[status as PhysicalOriginalStatus][locale],
      icon: physicalOriginalIcons[status as PhysicalOriginalStatus],
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
      data-status={status}
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
