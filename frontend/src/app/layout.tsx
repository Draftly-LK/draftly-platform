import type { Metadata } from "next";
import {
  IBM_Plex_Sans,
  Newsreader,
  Noto_Sans_Sinhala,
  Noto_Serif_Sinhala,
} from "next/font/google";
import { ClerkProvider } from "@clerk/nextjs";
import { NextIntlClientProvider } from "next-intl";
import { getLocale, getMessages, getTranslations } from "next-intl/server";
import { ProvisionGate } from "@/components/auth/provision-gate";
import { MultilingualProvider } from "@/components/shell/multilingual-provider";
import { isClerkConfigured } from "@/lib/auth/clerk";
import { isMultilingualEnabled } from "@/lib/i18n/multilingual";
import "@/styles/globals.css";

const plex = IBM_Plex_Sans({
  subsets: ["latin"],
  weight: ["400", "500", "600"],
  variable: "--font-plex",
  display: "swap",
});
const newsreader = Newsreader({
  subsets: ["latin"],
  variable: "--font-newsreader",
  display: "swap",
});
const notoSansSi = Noto_Sans_Sinhala({
  subsets: ["sinhala"],
  variable: "--font-noto-sans-si",
  display: "swap",
});
const notoSerifSi = Noto_Serif_Sinhala({
  subsets: ["sinhala"],
  variable: "--font-noto-serif-si",
  display: "swap",
});

export async function generateMetadata(): Promise<Metadata> {
  const t = await getTranslations("app");
  return { title: t("name"), description: t("metaDescription") };
}

export default async function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  const locale = await getLocale();
  const messages = await getMessages();
  const multilingual = isMultilingualEnabled();
  // ProvisionGate renders translated copy on its blocking-error state, so it
  // has to sit inside NextIntlClientProvider — not the other way around.
  const body = isClerkConfigured() ? (
    <ClerkProvider afterSignOutUrl="/sign-in">
      {/* Inside ClerkProvider: it reads the session to know when to run.
          Wraps the tree so first-time users reach onboarding before any
          workspace screen paints. */}
      <ProvisionGate>{children}</ProvisionGate>
    </ClerkProvider>
  ) : (
    children
  );

  return (
    <html
      lang={locale}
      className={`${plex.variable} ${newsreader.variable} ${notoSansSi.variable} ${notoSerifSi.variable}`}
    >
      {/* Browser extensions such as Grammarly add data attributes to body
          before React hydrates. Limit suppression to this host element so
          genuine mismatches inside the application remain visible. */}
      <body suppressHydrationWarning>
        <NextIntlClientProvider
          locale={locale}
          messages={messages}
          timeZone="Asia/Colombo"
        >
          <MultilingualProvider enabled={multilingual}>
            {body}
          </MultilingualProvider>
        </NextIntlClientProvider>
      </body>
    </html>
  );
}
