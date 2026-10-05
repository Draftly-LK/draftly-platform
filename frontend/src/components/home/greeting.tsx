"use client";

import { useUser } from "@clerk/nextjs";
import { useTranslations } from "next-intl";
import { partOfDay } from "@/lib/home/dashboard";
import { useDemoMode } from "@/components/shell/user-button";
import { useLocalHour } from "./matter-feed";

function GreetingText({ name }: { name: string }) {
  const t = useTranslations("home");
  const hour = useLocalHour();
  const args = { hasName: name ? "true" : "false", name };
  // Until the browser reports the local hour the greeting is neutral, so the
  // server-rendered text never claims a time of day it cannot know.
  const text =
    hour === null
      ? t("greetingWelcome", args)
      : partOfDay(hour) === "morning"
        ? t("greetingMorning", args)
        : partOfDay(hour) === "afternoon"
          ? t("greetingAfternoon", args)
          : t("greetingEvening", args);
  return (
    <h1 id="home-title" className="font-display text-3xl font-semibold leading-tight">
      {text}
    </h1>
  );
}

function ClerkGreeting() {
  const { user } = useUser();
  return <GreetingText name={user?.firstName?.trim() ?? ""} />;
}

/** "Good morning, Praveen" by the user's local time; no name in the offline demo. */
export function Greeting() {
  return useDemoMode() ? <GreetingText name="" /> : <ClerkGreeting />;
}
