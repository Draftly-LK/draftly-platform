import type { ApiFormField } from "@/types/rta";

/** Where a bound field stands, shown as icon + text on the page and in review. */
export type FieldStatus = "unresolved" | "awaiting" | "confirmed";

const UNRESOLVED_TOKEN = "[[UNRESOLVED:";

export function isUnresolved(field: Pick<ApiFormField, "displayValue">): boolean {
  return field.displayValue.includes(UNRESOLVED_TOKEN);
}

export function fieldStatus(
  field: Pick<ApiFormField, "displayValue" | "awaitingConfirmation">,
): FieldStatus {
  if (isUnresolved(field)) return "unresolved";
  return field.awaitingConfirmation ? "awaiting" : "confirmed";
}

/** The value to print in the blank, or null while the field is unresolved. */
export function printedValue(field: Pick<ApiFormField, "displayValue">): string | null {
  return isUnresolved(field) ? null : field.displayValue;
}

/** Free-text blanks the lawyer fills directly, keyed by slot id. */
export type SlotValues = Record<string, string>;

/** How many blanks carry something: a printed field value or typed text. */
export function countFilled(
  slots: Array<{ id: string; field: string | null }>,
  fields: Record<string, Pick<ApiFormField, "displayValue">>,
  values: SlotValues,
): number {
  return slots.filter((slot) => {
    if (slot.field) {
      const field = fields[slot.field];
      return field ? printedValue(field) !== null : false;
    }
    return (values[slot.id] ?? "").trim().length > 0;
  }).length;
}
