/**
 * Every ICU placeholder must be supplied by the component that renders it.
 *
 * next-intl throws `IntlError: MISSING_FORMAT_VALUE` at runtime when a message
 * declares `{count}` and the caller passes nothing, so this is a console error
 * a user sees rather than a lint warning a developer sees.
 */

import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";
import en from "./en.json";
import si from "./si.json";

const MESSAGES: Record<string, Record<string, unknown>> = {
  en: en as Record<string, unknown>,
  si: si as Record<string, unknown>,
};

/** Namespace and keys the documents screen renders with a count. */
const DOCUMENT_COUNT_KEYS = [
  "totalDocuments",
  "boundaryReview",
  "classificationReview",
  "unidentified",
  "unprocessed",
] as const;

const DOCUMENTS_SCREEN = join(
  process.cwd(),
  "src",
  "components",
  "matter",
  "documents-screen.tsx",
);

describe("documents screen count arguments", () => {
  const source = readFileSync(DOCUMENTS_SCREEN, "utf-8");

  it.each(DOCUMENT_COUNT_KEYS)(
    "%s is called with a count argument",
    (key) => {
      // `t("key")` with no second argument is the failure mode; require the
      // call site to pass `count`.
      const bare = new RegExp(`t\\("${key}"\\)`);
      expect(source).not.toMatch(bare);
      const withCount = new RegExp(`t\\("${key}",\\s*\\{[\\s\\S]{0,120}?count:`);
      expect(source).toMatch(withCount);
    },
  );
});

describe("locale catalogues", () => {
  it.each(Object.keys(MESSAGES))(
    "%s defines matterNav.assistantTab",
    (locale) => {
      const nav = MESSAGES[locale]?.matterNav as Record<string, string>;
      expect(nav?.assistantTab).toBeTruthy();
    },
  );

  it.each(Object.keys(MESSAGES))("%s defines the matter assistant screen", (locale) => {
    const screen = MESSAGES[locale]?.matterAssistant as Record<string, string>;
    for (const key of ["title", "send", "confirm", "reject", "retry", "thread"]) {
      expect(screen?.[key], `${locale}.matterAssistant.${key}`).toBeTruthy();
    }
  });

  it("declares the same count placeholders in every locale", () => {
    for (const key of DOCUMENT_COUNT_KEYS) {
      const declares = Object.keys(MESSAGES).map((locale) => {
        const found = findMessage(MESSAGES[locale] ?? {}, key);
        return found?.includes("{count}") ?? false;
      });
      // A placeholder present in one locale and absent in another throws only
      // for the locale that has it, which is the worst kind of bug to find.
      expect(new Set(declares).size, `${key} differs across locales`).toBe(1);
    }
  });
});

function findMessage(
  node: Record<string, unknown>,
  key: string,
): string | undefined {
  for (const [name, value] of Object.entries(node)) {
    if (name === key && typeof value === "string") return value;
    if (value && typeof value === "object") {
      const nested = findMessage(value as Record<string, unknown>, key);
      if (nested !== undefined) return nested;
    }
  }
  return undefined;
}
