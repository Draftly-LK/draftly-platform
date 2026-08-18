/**
 * Pure helpers for the profile screen's editable fields.
 *
 * Deliberately free of React/Clerk imports so these are unit-testable in
 * isolation. `EDITABLE_PROFILE_FIELDS` is the single source of truth for
 * "which fields does the profile screen let a user edit" — `EditableProfile`,
 * `ProfileUpdate` (lib/api/auth.ts) and the demo store's patch type all derive
 * from it rather than repeating the list.
 */

import type { ProfileUpdate } from "@/lib/api/auth";
import type { User } from "@/types";

/**
 * Every field the profile screen edits. Must stay a subset of the keys
 * `ProfileUpdate` accepts (mirrors backend `EDITABLE_PROFILE_FIELDS`), and of
 * `User` (the demo store's own shape for the same data).
 */
export const EDITABLE_PROFILE_FIELDS = [
  "displayName",
  "professionalTitles",
  "qualifications",
  "notaryRegistration",
  "jurisdiction",
  "addressLine1",
  "addressLine2",
  "phone",
] as const satisfies readonly (keyof ProfileUpdate & keyof User)[];

export type EditableProfile = Pick<User, (typeof EDITABLE_PROFILE_FIELDS)[number]>;

/** A changed-fields diff, ready to send as-is to `PATCH /me` or the demo store. */
export type ProfileFieldPatch = ProfileUpdate;

/**
 * Only fields that actually changed, diffed against the last-saved values.
 *
 * Clear-on-null: a field that **was** non-blank and is now blank emits an
 * explicit `null` — the backend (and the demo store) treat `null` as "clear
 * this column". A field that was already blank and stays blank is omitted
 * entirely, so a no-op edit never touches a column the user didn't mean to
 * change. A genuine change (including blank → non-blank) sends the trimmed
 * string.
 *
 * This deliberately differs from onboarding's `toProfileUpdate`
 * (components/auth/onboarding-screen.tsx): a first-run form has no "original"
 * to diff against, so it always drops blanks instead of clearing anything.
 */
export function diffProfile(original: EditableProfile, draft: EditableProfile): ProfileFieldPatch {
  const changes: ProfileFieldPatch = {};
  for (const key of EDITABLE_PROFILE_FIELDS) {
    const originalTrimmed = original[key].trim();
    const draftTrimmed = draft[key].trim();
    if (draftTrimmed === originalTrimmed) continue;
    changes[key] = draftTrimmed.length > 0 ? draftTrimmed : null;
  }
  return changes;
}

/** Picks the editable fields off a `User`-shaped record (e.g. the demo store's profile). */
export function pickEditableProfile(user: User): EditableProfile {
  const result = {} as EditableProfile;
  for (const key of EDITABLE_PROFILE_FIELDS) {
    result[key] = user[key];
  }
  return result;
}

/** Coerces a wire user's nullable fields (e.g. `ApiUser`) into an `EditableProfile`. */
export function toEditableProfile(
  user: Record<(typeof EDITABLE_PROFILE_FIELDS)[number], string | null>,
): EditableProfile {
  const result = {} as EditableProfile;
  for (const key of EDITABLE_PROFILE_FIELDS) {
    result[key] = user[key] ?? "";
  }
  return result;
}
