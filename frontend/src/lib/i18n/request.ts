import { getRequestConfig } from "next-intl/server";
import en from "./messages/en.json";
import si from "./messages/si.json";
import { cookies } from "next/headers";
import { messageFallback } from "./humanize";
import { LOCALE_COOKIE, parseLocaleCookie } from "./multilingual";

export default getRequestConfig(async () => {
  const locale = parseLocaleCookie((await cookies()).get(LOCALE_COOKIE)?.value);
  return {
    locale,
    messages: locale === "si" ? si : en,
    timeZone: "Asia/Colombo",
    getMessageFallback: messageFallback,
  };
});
