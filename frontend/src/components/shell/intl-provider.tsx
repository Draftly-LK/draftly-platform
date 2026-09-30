"use client";

import { NextIntlClientProvider } from "next-intl";
import { messageFallback } from "@/lib/i18n/humanize";

/**
 * `NextIntlClientProvider` with the readable missing-message fallback.
 *
 * A function cannot cross from the server layout into a client provider as a
 * prop, so the fallback is bound here. Missing keys are still reported through
 * next-intl's default `onError`; only what the user sees changes.
 */
export function IntlProvider({
  locale,
  messages,
  timeZone,
  children,
}: {
  locale: string;
  messages: Record<string, unknown>;
  timeZone: string;
  children: React.ReactNode;
}) {
  return (
    <NextIntlClientProvider
      locale={locale}
      messages={messages}
      timeZone={timeZone}
      getMessageFallback={messageFallback}
    >
      {children}
    </NextIntlClientProvider>
  );
}
