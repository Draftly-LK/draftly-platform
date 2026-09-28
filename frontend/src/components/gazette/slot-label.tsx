"use client";

import { useTranslations } from "next-intl";
import type { SlotInfo } from "@/lib/gazette-forms";

/**
 * A blank's name. Entries use the printed caption verbatim (it is the form's
 * own wording, not UI copy); blanks inside prose or tables use a translated
 * description, because the page gives them no caption of their own.
 */
export function useSlotLabel(): (slot: SlotInfo) => string {
  const t = useTranslations("gazette.slot");
  return (slot) => {
    if (slot.labelKey) return t(slot.labelKey);
    const caption = slot.caption ?? "";
    return slot.itemNumber ? `${slot.itemNumber} ${slot.itemTitle ?? ""} — ${caption}` : caption;
  };
}
