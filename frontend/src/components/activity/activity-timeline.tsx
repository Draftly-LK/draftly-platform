"use client";

import { Clock3 } from "lucide-react";
import { useLocale, useTranslations } from "next-intl";
import { useDemoStore } from "@/lib/store";

export function ActivityTimeline({ matterId }: { matterId?: string }) {
  const t = useTranslations("activity");
  const locale = useLocale() === "si" ? "si-LK" : "en-LK";
  const allEvents = useDemoStore((state) => state.auditEvents);
  const events = (
    matterId
      ? allEvents.filter((event) => event.matterId === matterId)
      : allEvents
  ).toReversed();
  if (!events.length)
    return <p className="text-muted-ink p-6">{t("noEvents")}</p>;
  return (
    <ol className="border-border-strong relative border-l">
      {events.map((event) => (
        <li
          key={event.id}
          className="border-border relative ml-6 border-b py-4 last:border-b-0"
        >
          <span className="border-forest bg-soft-green absolute -left-[33px] top-5 grid size-4 place-items-center rounded-full border">
            <Clock3 className="text-forest size-2.5" strokeWidth={1.5} />
          </span>
          <div className="flex flex-wrap items-start justify-between gap-2">
            <div>
              <div className="font-medium">
                {t("event", { action: event.action })}
              </div>
              <div className="text-muted-ink mt-1 text-xs">
                {t("actor", { actor: event.actor })} ·{" "}
                {t("target", { type: event.targetType, id: event.targetId })}
              </div>
            </div>
            <div className="text-muted-ink text-xs tabular-nums">
              {new Intl.DateTimeFormat(locale, {
                dateStyle: "medium",
                timeStyle: "short",
                timeZone: "Asia/Colombo",
              }).format(new Date(event.timestamp))}
            </div>
          </div>
          <span className="border-border-strong mt-2 inline-block rounded-full border px-2 py-1 text-xs">
            {event.id.startsWith("audit-live")
              ? t("liveSession")
              : t("historical")}
          </span>
        </li>
      ))}
    </ol>
  );
}
