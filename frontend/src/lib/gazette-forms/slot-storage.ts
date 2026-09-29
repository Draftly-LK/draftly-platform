import type { SlotValues } from "./field-state";

/*
 * Free-text blanks have no backend endpoint yet: the draft API stores field
 * decisions only. Until one exists they are kept on this device, per form,
 * and the screen says so. Storage can be unavailable (private windows,
 * blocked site data), so every access is guarded and failure means "empty".
 */

const PREFIX = "draftly.gazette.slots.v1.";

export function loadSlotValues(formId: string, storage: Storage | undefined = globalStorage()): SlotValues {
  try {
    const raw = storage?.getItem(PREFIX + formId);
    if (!raw) return {};
    const parsed: unknown = JSON.parse(raw);
    if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) return {};
    return Object.fromEntries(
      Object.entries(parsed as Record<string, unknown>).filter(
        (entry): entry is [string, string] => typeof entry[1] === "string",
      ),
    );
  } catch {
    return {};
  }
}

export function saveSlotValues(
  formId: string,
  values: SlotValues,
  storage: Storage | undefined = globalStorage(),
): boolean {
  try {
    if (!storage) return false;
    storage.setItem(PREFIX + formId, JSON.stringify(values));
    return true;
  } catch {
    return false;
  }
}

function globalStorage(): Storage | undefined {
  try {
    return typeof window === "undefined" ? undefined : window.localStorage;
  } catch {
    return undefined;
  }
}
