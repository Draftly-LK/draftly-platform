import type { Metadata } from "next";
import { IBM_Plex_Sans, Noto_Sans_Sinhala, Noto_Serif_Sinhala, Source_Serif_4 } from "next/font/google";
import { ClerkProvider } from "@clerk/nextjs";
import { getLocale, getMessages, getTranslations } from "next-intl/server";
import { ProvisionGate } from "@/components/auth/provision-gate";
import { IntlProvider } from "@/components/shell/intl-provider";
import { NavigationProgress } from "@/components/shell/navigation-progress";
import { UserButtonProvider } from "@/components/shell/user-button";
import { isAuthBypassEnabled } from "@/lib/auth/bypass";
import { hasClerkPublishableKey, isClerkConfigured } from "@/lib/auth/clerk";
import "@/styles/globals.css";

const plex = IBM_Plex_Sans({
  subsets: ["latin"],
  weight: ["400", "500", "600"],
  variable: "--font-plex",
  display: "swap",
});
const notoSansSi = Noto_Sans_Sinhala({
  subsets: ["sinhala"],
  variable: "--font-noto-sans-si",
  display: "swap",
});
// Display face for page titles and the wordmark: a legal-register serif,
// paired with its Sinhala counterpart so a Sinhala title keeps the same voice.
const sourceSerif = Source_Serif_4({
  subsets: ["latin"],
  weight: ["500", "600", "700"],
  variable: "--font-serif",
  display: "swap",
});
const notoSerifSi = Noto_Serif_Sinhala({
  subsets: ["sinhala"],
  weight: ["500", "600", "700"],
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
  // ProvisionGate renders translated copy on its blocking-error state, so it
  // has to sit inside IntlProvider — not the other way around.
  //
  // The provider follows the public key alone, as `useTokenProvider` does: a
  // Docker build inlines the publishable key but gets CLERK_SECRET_KEY only at
  // run time, and prerendering a screen that calls `useAuth` without a
  // provider fails the build.
  const body = hasClerkPublishableKey() ? (
    <ClerkProvider afterSignOutUrl="/sign-in">
      {/* Inside ClerkProvider: it reads the session to know when to run.
          Wraps the tree so first-time users reach onboarding before any
          workspace screen paints. */}
      {isClerkConfigured() ? <ProvisionGate>{children}</ProvisionGate> : children}
    </ClerkProvider>
  ) : (
    children
  );

  return (
    <html lang={locale} className={`${plex.variable} ${notoSansSi.variable} ${sourceSerif.variable} ${notoSerifSi.variable}`}>
      {/* Browser extensions such as Grammarly add data attributes to body
          before React hydrates. Limit suppression to this host element so
          genuine mismatches inside the application remain visible. */}
      <body suppressHydrationWarning>
        <IntlProvider
          locale={locale}
          messages={messages as Record<string, unknown>}
          timeZone="Asia/Colombo"
        >
          {/* Resolved here, on the server: AUTH_BYPASS and CLERK_SECRET_KEY
              are undefined in the browser, where most screens render. */}
          <NavigationProgress />
          <UserButtonProvider demoMode={isAuthBypassEnabled() || !isClerkConfigured()}>
            {body}
          </UserButtonProvider>
        </IntlProvider>
      </body>
    </html>
  );
}
