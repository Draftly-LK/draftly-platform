"use client";

import { createContext, useContext } from "react";
import type { SlotValues } from "@/lib/gazette-forms/field-state";
import type { SlotInfo } from "@/lib/gazette-forms";
import type { ApiFormField } from "@/types/rta";

/**
 * What the blanks on the page read and write. Both drafting modes share one
 * instance, so a value entered field by field is the value on the page and
 * the reverse.
 */
export interface GazetteContextValue {
  /** Typed text for free blanks, keyed by slot id. */
  values: SlotValues;
  setValue: (slotId: string, value: string) => void;
  /** Bound backend fields, keyed by `fieldId`. */
  fields: Record<string, ApiFormField>;
  slots: Record<string, SlotInfo>;
  activeSlotId: string | null;
  activate: (slotId: string) => void;
  /** True once the form is approved: nothing on it may change. */
  readOnly: boolean;
  /** Draw blanks as the printed page does (dotted leaders, no values). */
  plain?: boolean;
}

export const GazetteContext = createContext<GazetteContextValue | null>(null);

export function useGazette(): GazetteContextValue {
  const value = useContext(GazetteContext);
  if (!value) throw new Error("useGazette must be used inside GazetteContext");
  return value;
}
