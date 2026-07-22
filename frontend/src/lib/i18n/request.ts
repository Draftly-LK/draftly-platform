import { cookies } from "next/headers";
import { getRequestConfig } from "next-intl/server";
import en from "./messages/en.json";
import si from "./messages/si.json";

export default getRequestConfig(async () => {
  const cookieStore = await cookies();
  const requested = cookieStore.get("draftly-locale")?.value;
  const locale = requested === "si" ? "si" : "en";
  const messages = locale === "si" ? si : en;
  return { locale, messages };
});
