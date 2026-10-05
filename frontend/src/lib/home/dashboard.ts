import type { useFormatter } from "next-intl";
import type { RtaMatterState } from "@/types/rta";
import { NEEDS_REVIEW } from "./practice-snapshot";

/* Pure helpers for the dashboard. Nothing here reads the clock: callers pass
   `now`, so the demo can pin it to the fixture date and tests stay exact. */

export type PartOfDay = "morning" | "afternoon" | "evening";

/** By the user's local hour: 05-11 morning, 12-16 afternoon, otherwise evening. */
export function partOfDay(hour: number): PartOfDay {
  if (hour >= 5 && hour < 12) return "morning";
  if (hour >= 12 && hour < 17) return "afternoon";
  return "evening";
}

export function needsReview(state: RtaMatterState): boolean {
  return NEEDS_REVIEW.has(state);
}

interface Sortable {
  state: RtaMatterState;
  updatedAt: string;
}

/** Review-required matters first (a priority, not decoration), then newest activity. */
export function sortForDashboard<T extends Sortable>(matters: readonly T[]): T[] {
  return [...matters].sort((a, b) => {
    const reviewDelta = Number(needsReview(b.state)) - Number(needsReview(a.state));
    if (reviewDelta !== 0) return reviewDelta;
    return Date.parse(b.updatedAt) - Date.parse(a.updatedAt);
  });
}

export type StatusTone = "neutral" | "success" | "warning" | "danger" | "info";

/** Tone of a matter's state chip. The chip always pairs this with an icon and the state's name. */
export function stateTone(state: RtaMatterState): StatusTone {
  if (needsReview(state) || state === "LITIGATION_HOLD") return "warning";
  switch (state) {
    case "APPROVED":
    case "EXPORTED":
    case "SUBMITTED":
    case "REGISTERED":
      return "success";
    case "INTAKE_DRAFT":
    case "ROUTED":
    case "EVIDENCE_COLLECTION":
    case "READY_TO_DRAFT":
    case "DRAFTING":
      return "info";
    default:
      return "neutral";
  }
}

const DAY_MS = 86_400_000;

/** Whole calendar days from `now` to a `YYYY-MM-DD` due date, in UTC. Negative when overdue. */
export function daysUntil(dueDate: string, now: Date): number {
  const due = Date.parse(`${dueDate}T00:00:00Z`);
  const today = Date.UTC(now.getUTCFullYear(), now.getUTCMonth(), now.getUTCDate());
  return Math.round((due - today) / DAY_MS);
}

export type DueLabel =
  | { kind: "overdue"; days: number }
  | { kind: "today" }
  | { kind: "in"; days: number }
  | { kind: "date" };

/** "Overdue by 2 days", "Due today", "In 2 days"; beyond a week the caller prints the date. */
export function dueLabel(days: number): DueLabel {
  if (days < 0) return { kind: "overdue", days: -days };
  if (days === 0) return { kind: "today" };
  if (days <= 7) return { kind: "in", days };
  return { kind: "date" };
}

/** Overdue is danger, due within two days is warning, everything else is quiet. */
export function dueTone(days: number): StatusTone {
  if (days < 0) return "danger";
  if (days <= 2) return "warning";
  return "neutral";
}

interface Dated {
  dueDate: string;
}

/** Most urgent first: the longest overdue, then the soonest due. */
export function sortByUrgency<T extends Dated>(items: readonly T[]): T[] {
  return [...items].sort((a, b) => a.dueDate.localeCompare(b.dueDate));
}

/** Obligations inside the horizon (overdue ones always count). */
export function dueWithin<T extends Dated>(items: readonly T[], now: Date, horizonDays = 14): T[] {
  return items.filter((item) => daysUntil(item.dueDate, now) <= horizonDays);
}

/** Relative wording ("2 hours ago", "yesterday") inside a week, an absolute day-month after. */
export function activityIsRecent(updatedAt: string, now: Date): boolean {
  const age = now.getTime() - Date.parse(updatedAt);
  return age >= 0 && age < 7 * DAY_MS;
}

type DateFormatter = ReturnType<typeof useFormatter>;

/** "31 Jul": day before month, the Sri Lankan convention, in any interface language. */
export function dayMonth(format: DateFormatter, date: Date, timeZone?: string): string {
  const options = { calendar: "gregory", numberingSystem: "latn", ...(timeZone ? { timeZone } : {}) } as const;
  return `${format.dateTime(date, { ...options, day: "numeric" })} ${format.dateTime(date, { ...options, month: "short" })}`;
}
