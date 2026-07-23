import type { Metadata } from "next";
import {
  Abhaya_Libre,
  IBM_Plex_Sans,
  Newsreader,
  Noto_Sans_Sinhala,
  Noto_Serif_Sinhala,
} from "next/font/google";
import { NextIntlClientProvider } from "next-intl";
import { getLocale, getMessages, getTranslations } from "next-intl/server";
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
  weight: ["400", "500", "600", "700"],
  variable: "--font-noto-serif-si",
  display: "swap",
});
/** Sinhala serif closer to gazette/print forms (FM Abhaya family). */
const abhayaLibre = Abhaya_Libre({
  subsets: ["sinhala", "latin"],
  weight: ["400", "500", "600", "700", "800"],
  variable: "--font-abhaya",
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
  return (
    <html
      lang={locale}
      className={`${plex.variable} ${newsreader.variable} ${notoSansSi.variable} ${notoSerifSi.variable} ${abhayaLibre.variable}`}
    >
      <body>
        <NextIntlClientProvider
          locale={locale}
          messages={messages}
          timeZone="Asia/Colombo"
        >
          {children}
        </NextIntlClientProvider>
      </body>
    </html>
  );
}
