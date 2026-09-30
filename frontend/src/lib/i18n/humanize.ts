/**
 * Last-resort text for a message key that has no catalogue entry.
 *
 * next-intl's default fallback prints the key itself (`namespace.some.KEY`),
 * which is meaningless to a lawyer. Missing keys are still reported through
 * `onError` so they get fixed, but what the user sees is a readable phrase
 * derived from the key: `gazette.unresolvedReason.NO_FACT` → "No fact".
 */

/** Trailing segments that describe the slot, not the thing (`…district.label`). */
const SLOT_SEGMENTS = new Set(["label", "title", "body", "description", "purpose", "text", "name"]);

function words(segment: string): string {
  const spaced = segment
    .replace(/([a-z0-9])([A-Z])/g, "$1 $2")
    .replace(/[_\-.]+/g, " ")
    .replace(/\s+/g, " ")
    .trim()
    .toLowerCase();
  return spaced.charAt(0).toUpperCase() + spaced.slice(1);
}

export function humanizeMessageKey(key: string): string {
  const segments = key.split(".").filter((segment) => segment.length > 0);
  if (segments.length === 0) return "";
  let index = segments.length - 1;
  while (index > 0 && SLOT_SEGMENTS.has(segments[index]!.toLowerCase())) index -= 1;
  return words(segments[index]!);
}

/** Shape of next-intl's `getMessageFallback` argument (server and client). */
export function messageFallback({ key }: { namespace?: string; key: string }): string {
  return humanizeMessageKey(key);
}
