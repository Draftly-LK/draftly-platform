"use client";

import { useTranslations } from "next-intl";
import { humanizeMessageKey } from "./humanize";

/**
 * Label for a backend enum value: `enums.<group>.<VALUE>` from the catalogue,
 * or a readable phrase derived from the value when the catalogue has no entry
 * (a new backend value must never reach the screen as `SOME_CODE`).
 *
 * Use it wherever a wire value would otherwise be printed:
 * `const stateLabel = useEnumLabel("enums.sourceFileState")`.
 */
export function useEnumLabel(prefix: string): (value: string | null | undefined) => string {
  const t = useTranslations();
  return (value) => {
    if (!value) return "";
    const key = `${prefix}.${value}`;
    return t.has(key) ? t(key) : humanizeMessageKey(value);
  };
}
