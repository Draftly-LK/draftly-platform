"use client";

import { useEffect, useState, type ReactNode } from "react";
import { isApiEnabled } from "@/lib/api/client";
import { useRecentMatters } from "@/lib/api/use-recent-matters";
import { FIXED_NOW, matters as demoMatters } from "@/lib/mocks";
import { migrateLegacyMatterType } from "@/lib/rta/taxonomy";
import type { ApiRtaMatter } from "@/types/rta";

export interface Feed {
  matters: ApiRtaMatter[];
  loading: boolean;
  failed: boolean;
}

/** The offline demo's fixture matters in the API's shape. */
export function demoMatterFeed(): ApiRtaMatter[] {
  return demoMatters.map(
    (matter) =>
      ({
        id: matter.id,
        reference: matter.reference,
        clientReference: matter.parties.map((party) => party.nameToken).join(" / "),
        subtypeId: matter.subtypeId ?? migrateLegacyMatterType(matter.type)?.subtypeId ?? null,
        state: matter.status === "in-review" ? "REVIEW_REQUIRED" : "APPROVED",
        updatedAt: matter.updatedAt,
      }) as ApiRtaMatter,
  );
}

/**
 * One source of matters for every part of the dashboard, so the header line,
 * the counts and the list can never disagree. Render-prop so the API hook is
 * only ever called in API mode.
 */
export function MatterFeed({ children }: { children: (feed: Feed) => ReactNode }) {
  return isApiEnabled() ? (
    <ApiFeed>{children}</ApiFeed>
  ) : (
    <>{children({ matters: demoMatterFeed(), loading: false, failed: false })}</>
  );
}

function ApiFeed({ children }: { children: (feed: Feed) => ReactNode }) {
  const { matters, loading, failed } = useRecentMatters();
  return <>{children({ matters, loading, failed })}</>;
}

// Two hours after the fixture's last activity, so the demo reads "2 hours ago" and not "now".
const DEMO_CLOCK_OFFSET_MS = 2 * 60 * 60 * 1000;

/**
 * "Today" for relative dates. The offline demo is pinned to its fixture date so
 * the page is deterministic; a live workspace uses the real clock, read after
 * mount so server and client markup agree. Null until then.
 */
export function useDashboardNow(): Date | null {
  const demo = !isApiEnabled();
  const [now, setNow] = useState<Date | null>(null);
  useEffect(() => {
    setNow(demo ? new Date(Date.parse(FIXED_NOW) + DEMO_CLOCK_OFFSET_MS) : new Date());
  }, [demo]);
  return now;
}

/** Local hour of day, read after mount (null before), for the greeting. */
export function useLocalHour(): number | null {
  const [hour, setHour] = useState<number | null>(null);
  useEffect(() => {
    setHour(new Date().getHours());
  }, []);
  return hour;
}
