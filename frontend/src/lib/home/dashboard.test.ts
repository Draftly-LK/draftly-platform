import { describe, expect, it } from "vitest";
import {
  activityIsRecent,
  daysUntil,
  dueLabel,
  dueTone,
  dayMonth,
  dueWithin,
  needsReview,
  partOfDay,
  sortByUrgency,
  sortForDashboard,
  stateTone,
} from "./dashboard";

const NOW = new Date("2026-07-22T09:30:00.000Z");

describe("partOfDay", () => {
  it.each([
    [5, "morning"],
    [11, "morning"],
    [12, "afternoon"],
    [16, "afternoon"],
    [17, "evening"],
    [23, "evening"],
    [3, "evening"],
  ] as const)("hour %i is %s", (hour, expected) => {
    expect(partOfDay(hour)).toBe(expected);
  });
});

describe("sortForDashboard", () => {
  it("puts review-required matters first, then newest activity", () => {
    const sorted = sortForDashboard([
      { id: "a", state: "DRAFTING", updatedAt: "2026-07-22T10:00:00Z" },
      { id: "b", state: "REVIEW_REQUIRED", updatedAt: "2026-07-01T10:00:00Z" },
      { id: "c", state: "APPROVED", updatedAt: "2026-07-21T10:00:00Z" },
      { id: "d", state: "LEGAL_REVIEW", updatedAt: "2026-07-10T10:00:00Z" },
    ] as const);
    expect(sorted.map((m) => m.id)).toEqual(["d", "b", "a", "c"]);
  });

  it("does not change the input", () => {
    const input = [
      { state: "DRAFTING", updatedAt: "2026-07-01T00:00:00Z" },
      { state: "REVIEW_REQUIRED", updatedAt: "2026-06-01T00:00:00Z" },
    ] as const;
    sortForDashboard(input);
    expect(input[0].state).toBe("DRAFTING");
  });
});

describe("states", () => {
  it("knows which states wait on the lawyer", () => {
    expect(needsReview("REVIEW_REQUIRED")).toBe(true);
    expect(needsReview("DRAFTING")).toBe(false);
  });

  it.each([
    ["REVIEW_REQUIRED", "warning"],
    ["LITIGATION_HOLD", "warning"],
    ["APPROVED", "success"],
    ["DRAFTING", "info"],
    ["CLOSED", "neutral"],
  ] as const)("%s reads as %s", (state, tone) => {
    expect(stateTone(state)).toBe(tone);
  });
});

describe("due dates", () => {
  it("counts whole days from today, negative when overdue", () => {
    expect(daysUntil("2026-07-22", NOW)).toBe(0);
    expect(daysUntil("2026-07-24", NOW)).toBe(2);
    expect(daysUntil("2026-07-20", NOW)).toBe(-2);
  });

  it("labels overdue, today, soon and later", () => {
    expect(dueLabel(-2)).toEqual({ kind: "overdue", days: 2 });
    expect(dueLabel(0)).toEqual({ kind: "today" });
    expect(dueLabel(2)).toEqual({ kind: "in", days: 2 });
    expect(dueLabel(7)).toEqual({ kind: "in", days: 7 });
    expect(dueLabel(8)).toEqual({ kind: "date" });
  });

  it("styles overdue as danger and the next two days as warning", () => {
    expect(dueTone(-1)).toBe("danger");
    expect(dueTone(0)).toBe("warning");
    expect(dueTone(2)).toBe("warning");
    expect(dueTone(3)).toBe("neutral");
  });

  it("sorts by urgency and keeps only what is due within the horizon", () => {
    const items = [
      { id: "late", dueDate: "2026-08-15" },
      { id: "over", dueDate: "2026-07-01" },
      { id: "soon", dueDate: "2026-07-24" },
    ];
    expect(sortByUrgency(items).map((i) => i.id)).toEqual(["over", "soon", "late"]);
    expect(dueWithin(items, NOW).map((i) => i.id)).toEqual(["over", "soon"]);
    expect(dueWithin(items, NOW, 30).map((i) => i.id)).toEqual(["late", "over", "soon"]);
  });
});

describe("activityIsRecent", () => {
  it("uses relative wording inside a week and a date after", () => {
    expect(activityIsRecent("2026-07-22T07:30:00Z", NOW)).toBe(true);
    expect(activityIsRecent("2026-07-16T09:30:01Z", NOW)).toBe(true);
    expect(activityIsRecent("2026-07-10T09:30:00Z", NOW)).toBe(false);
    expect(activityIsRecent("2026-07-23T09:30:00Z", NOW)).toBe(false);
  });
});

describe("dayMonth", () => {
  const format = {
    dateTime: (date: Date, options: Intl.DateTimeFormatOptions) => new Intl.DateTimeFormat("en", options).format(date),
  } as unknown as Parameters<typeof dayMonth>[0];

  it("puts the day before the month", () => {
    expect(dayMonth(format, new Date("2026-07-31T00:00:00Z"), "UTC")).toBe("31 Jul");
    expect(dayMonth(format, new Date("2026-08-05T00:00:00Z"), "UTC")).toBe("5 Aug");
  });
});
