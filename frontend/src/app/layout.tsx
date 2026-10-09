import type { Metadata } from "next";
import localFont from "next/font/local";
import { ClerkProvider } from "@clerk/nextjs";
import { cookies } from "next/headers";
import { getLocale, getMessages, getTranslations } from "next-intl/server";
import { ProvisionGate } from "@/components/auth/provision-gate";
import { IntlProvider } from "@/components/shell/intl-provider";
import { NavigationProgress } from "@/components/shell/navigation-progress";
import { SidebarStateProvider } from "@/components/shell/sidebar-state";
import { UserButtonProvider } from "@/components/shell/user-button";
import { isAuthBypassEnabled } from "@/lib/auth/bypass";
import { parseSidebarCookie, SIDEBAR_COOKIE } from "@/lib/sidebar-cookie";
import { hasClerkPublishableKey, isClerkConfigured } from "@/lib/auth/clerk";
import { draftlyClerkLocalization } from "@/lib/auth/clerk-localization";
import "@/styles/globals.css";

const plex = localFont({
  src: "./fonts/ibm-plex-sans.woff2",
  weight: "400 600",
  style: "normal",
  variable: "--font-plex",
  display: "swap",
});
const notoSansSi = localFont({
  src: "./fonts/noto-sans-sinhala.woff2",
  weight: "100 900",
  style: "normal",
  variable: "--font-noto-sans-si",
  display: "swap",
});
// Display face for page titles and the wordmark: a legal-register serif,
// paired with its Sinhala counterpart so a Sinhala title keeps the same voice.
const sourceSerif = localFont({
  src: "./fonts/source-serif-4.woff2",
  weight: "500 700",
  style: "normal",
  adjustFontFallback: "Times New Roman",
  variable: "--font-serif",
  display: "swap",
});
const notoSerifSi = localFont({
  src: "./fonts/noto-serif-sinhala.woff2",
  weight: "500 700",
  style: "normal",
  adjustFontFallback: "Times New Roman",
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
  const tAuth = await getTranslations("auth");
  // The sidebar's collapsed choice is a cookie, read here so the first paint is already in the right state.
  const sidebarCollapsed = parseSidebarCookie(
    (await cookies()).get(SIDEBAR_COOKIE)?.value,
  );
  // ProvisionGate renders translated copy on its blocking-error state, so it
  // has to sit inside IntlProvider — not the other way around.
  //
  // The provider follows the public key alone, as `useTokenProvider` does: a
  // Docker build inlines the publishable key but gets CLERK_SECRET_KEY only at
  // run time, and prerendering a screen that calls `useAuth` without a
  // provider fails the build.
  const body = hasClerkPublishableKey() ? (
    <ClerkProvider
      afterSignOutUrl="/sign-in"
      localization={draftlyClerkLocalization(tAuth)}
    >
      {/* Inside ClerkProvider: it reads the session to know when to run.
          Wraps the tree so first-time users reach onboarding before any
          workspace screen paints. */}
      {isClerkConfigured() ? (
        <ProvisionGate>{children}</ProvisionGate>
      ) : (
        children
      )}
    </ClerkProvider>
  ) : (
    children
  );

  return (
    <html
      lang={locale}
      data-sidebar={sidebarCollapsed ? "collapsed" : "expanded"}
      className={`${plex.variable} ${notoSansSi.variable} ${sourceSerif.variable} ${notoSerifSi.variable}`}
    >
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
          <SidebarStateProvider initialCollapsed={sidebarCollapsed}>
            <UserButtonProvider
              demoMode={isAuthBypassEnabled() || !isClerkConfigured()}
            >
              {body}
            </UserButtonProvider>
          </SidebarStateProvider>
        </IntlProvider>
      </body>
    </html>
  );
}
