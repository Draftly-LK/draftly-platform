"use client";

import { useEffect, useState } from "react";
import { getBillingUsage } from "@/lib/api/billing";
import { isApiEnabled } from "@/lib/api/client";
import { listResearchConversations } from "@/lib/api/research";
import { useTokenProvider } from "@/lib/api/use-token-provider";
import { researchUsage, type ResearchUsage } from "@/lib/home/insights";
import type { ResearchConversation } from "@/types";

/** The home page's research figures, loaded once and shared by the header and the body. */
export interface ResearchOverview {
  state: "loading" | "ready" | "failed" | "offline";
  /** Every research conversation the lawyer has kept (archived ones are not listed), latest first. */
  conversations: ResearchConversation[] | null;
  /** This month's research allowance; null when billing did not answer. */
  usage: ResearchUsage | null;
}

export const OFFLINE_RESEARCH: ResearchOverview = { state: "offline", conversations: null, usage: null };

export function useResearchOverview(): ResearchOverview {
  const api = isApiEnabled();
  const getToken = useTokenProvider();
  const [overview, setOverview] = useState<ResearchOverview>(api ? { ...OFFLINE_RESEARCH, state: "loading" } : OFFLINE_RESEARCH);

  useEffect(() => {
    if (!api) return;
    const controller = new AbortController();
    // The allowance is a nice-to-have: if billing fails, the conversation figures still show.
    const usage = getBillingUsage(getToken, controller.signal)
      .then(researchUsage)
      .catch(() => null);
    Promise.all([listResearchConversations(getToken), usage])
      .then(([conversations, allowance]) => {
        if (controller.signal.aborted) return;
        const sorted = [...conversations].sort((a, b) => b.updatedAt.localeCompare(a.updatedAt));
        setOverview({ state: "ready", conversations: sorted, usage: allowance });
      })
      .catch(() => {
        if (!controller.signal.aborted) setOverview({ ...OFFLINE_RESEARCH, state: "failed" });
      });
    return () => controller.abort();
  }, [api, getToken]);

  return overview;
}
