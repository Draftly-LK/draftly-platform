import { getRequestConfig } from "next-intl/server";
import en from "./messages/en.json";
import { messageFallback } from "./humanize";
import { DEFAULT_LOCALE } from "./multilingual";

// English only: no language switch, and any stored locale cookie is ignored.
export default getRequestConfig(async () => ({
  locale: DEFAULT_LOCALE,
  messages: en,
  timeZone: "Asia/Colombo",
  getMessageFallback: messageFallback,
}));
