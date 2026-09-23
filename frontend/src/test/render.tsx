/**
 * Renders a component the way the app does: inside next-intl with the real
 * message catalogue, so a missing key fails the test instead of the page.
 *
 * Component test files opt into a DOM with `// @vitest-environment happy-dom`;
 * everything else keeps running in plain Node.
 */
import { cleanup, render } from "@testing-library/react";
import { NextIntlClientProvider } from "next-intl";
import type { ReactElement } from "react";
import { afterEach } from "vitest";
import en from "@/lib/i18n/messages/en.json";
import si from "@/lib/i18n/messages/si.json";

afterEach(cleanup);

const MESSAGES = { en, si };

export function renderWithIntl(ui: ReactElement, locale: "en" | "si" = "en") {
  return render(
    <NextIntlClientProvider
      locale={locale}
      messages={MESSAGES[locale]}
      timeZone="Asia/Colombo"
      onError={(error) => {
        throw error;
      }}
    >
      {ui}
    </NextIntlClientProvider>,
  );
}
