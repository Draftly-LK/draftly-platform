"use client";

import { useTranslations } from "next-intl";
import { useEffect, useState } from "react";
import { isApiEnabled } from "@/lib/api/client";
import { getChecklist } from "@/lib/api/matters";
import { useTokenProvider } from "@/lib/api/use-token-provider";
import { checklistPercent } from "@/lib/home/insights";
import { MiniRing } from "./charts";

/** Percent per matter, keyed by id and last update, so a revisit within the session does not refetch. */
const cache = new Map<string, number | null>();

/**
 * How far a matter's checklist has got, as a small ring and a percentage.
 * Nothing renders until the checklist answers, when none is compiled yet, or
 * offline, so a missing figure never reads as 0%.
 */
export function ChecklistProgress({ matterId, updatedAt }: { matterId: string; updatedAt: string }) {
  return isApiEnabled() ? <ApiChecklistProgress matterId={matterId} updatedAt={updatedAt} /> : null;
}

function ApiChecklistProgress({ matterId, updatedAt }: { matterId: string; updatedAt: string }) {
  const t = useTranslations("home.insights");
  const getToken = useTokenProvider();
  const key = `${matterId}@${updatedAt}`;
  const [percent, setPercent] = useState<number | null | undefined>(cache.get(key));

  useEffect(() => {
    if (cache.has(key)) {
      setPercent(cache.get(key));
      return;
    }
    let active = true;
    getChecklist(getToken, matterId)
      .then((checklist) => checklistPercent(checklist))
      .catch(() => null)
      .then((value) => {
        cache.set(key, value);
        if (active) setPercent(value);
      });
    return () => {
      active = false;
    };
  }, [getToken, key, matterId]);

  if (percent === null || percent === undefined) return null;
  const label = t("checklistProgress", { percent });
  return (
    <span className="text-muted-ink inline-flex items-center gap-1.5 text-xs tabular-nums" title={label}>
      <MiniRing percent={percent} label={label} />
      <span aria-hidden="true">{percent}%</span>
    </span>
  );
}
