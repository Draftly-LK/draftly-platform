import { cookies } from "next/headers";
import { getRequestConfig } from "next-intl/server";
import en from "./messages/en.json";
import si from "./messages/si.json";

export default getRequestConfig(async () => {
  const cookieStore = await cookies();
  const requested = cookieStore.get("draftly-locale")?.value;
  const locale = requested === "si" ? "si" : "en";
  const messages = locale === "si" ? mergeMessages(en, si) : en;
  return { locale, messages };
});

function mergeMessages(base: Record<string, unknown>, translated: Record<string, unknown>): Record<string, unknown> {
  return Object.fromEntries(Object.entries(base).map(([key, value]) => {
    const replacement = translated[key];
    if (isRecord(value) && isRecord(replacement)) return [key, mergeMessages(value, replacement)];
    return [key, replacement ?? value];
  }));
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}
