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
import { statusToneClasses, type StatusTone } from "./status-chip";

type Status =
  | VerificationState
  | SourceFileState
  | PhysicalOriginalStatus
  | CheckStatus
  | StepState;

/** Which tone each status takes; the classes live in status-chip.tsx. Every badge still carries an icon and its text. */
const tones: Record<Status, StatusTone> = {
  unreviewed: "neutral",
  verified: "success",
  corrected: "info",
  conflict: "warning",
  blocked: "danger",
  UPLOAD_INITIATED: "neutral",
  QUARANTINED: "warning",
  VALIDATED: "neutral",
  STORED: "neutral",
  PROCESSING: "info",
  PROCESSED: "success",
  PROCESSING_FAILED: "danger",
  REJECTED: "danger",
  SUPERSEDED: "neutral",
  NOT_REQUIRED: "neutral",
  UNKNOWN: "neutral",
  COPY_ONLY: "warning",
  ORIGINAL_REPORTED: "info",
  ORIGINAL_INSPECTED: "success",
  pass: "success",
  warning: "warning",
  fail: "danger",
  "needs-review": "info",
  "not-started": "neutral",
  "in-progress": "info",
  complete: "success",
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
        statusToneClasses[tones[status]],
        className,
      )}
    >
      <Icon aria-hidden="true" className="size-4" strokeWidth={1.5} />
      {label}
    </span>
  );
}
