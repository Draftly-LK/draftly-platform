"use client";

import { useEffect, useState, type ReactNode } from "react";
import { isApiEnabled } from "@/lib/api/client";
import { useRecentMatters } from "@/lib/api/use-recent-matters";
import { FIXED_NOW } from "@/lib/mocks";
import { useDemoStore } from "@/lib/store";
import type { Matter, MatterStatus } from "@/types";
import { migrateLegacyMatterType } from "@/lib/rta/taxonomy";
import type { ApiRtaMatter, RtaMatterState } from "@/types/rta";

export interface Feed {
  matters: ApiRtaMatter[];
  loading: boolean;
  failed: boolean;
}

/** The demo's coarse status on the API's state vocabulary, so filters and counts work the same offline. */
export function demoMatterState(status: MatterStatus): RtaMatterState {
  switch (status) {
    case "in-review":
    case "blocked":
      return "REVIEW_REQUIRED";
    case "ready-to-draft":
      return "READY_TO_DRAFT";
    case "closed":
      return "CLOSED";
    default:
      return "EVIDENCE_COLLECTION";
  }
}

/** The offline demo's matters in the API's shape. */
export function demoMatterFeed(matters: readonly Matter[]): ApiRtaMatter[] {
  return matters.map(
    (matter) =>
      ({
        id: matter.id,
        reference: matter.reference,
        clientReference: matter.parties.map((party) => party.nameToken).join(" / "),
        subtypeId: matter.subtypeId ?? migrateLegacyMatterType(matter.type)?.subtypeId ?? null,
        state: demoMatterState(matter.status),
        createdAt: matter.createdAt,
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
  return isApiEnabled() ? <ApiFeed>{children}</ApiFeed> : <DemoFeed>{children}</DemoFeed>;
}

function DemoFeed({ children }: { children: (feed: Feed) => ReactNode }) {
  const matters = useDemoStore((state) => state.matters);
  return <>{children({ matters: demoMatterFeed(matters), loading: false, failed: false })}</>;
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
