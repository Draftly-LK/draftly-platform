import { apiFetch, type TokenProvider } from "./client";

export interface BillingSubscription {
  id: string;
  userId: string;
  planVersionId: string;
  provider: string;
  status: string;
  currentPeriodStart: string;
  currentPeriodEnd: string;
  trialEndsAt: string | null;
  cancelAtPeriodEnd: boolean;
  gracePeriodEndsAt: string | null;
  version: number;
}

export function getBillingSubscription(
  getToken: TokenProvider,
  signal?: AbortSignal,
): Promise<BillingSubscription> {
  return apiFetch<BillingSubscription>("/api/v1/billing/subscription", {
    getToken,
    signal,
  });
}

export interface BillingUsage {
  metric: string;
  quantity: number;
  periodStart: string;
  periodEnd: string;
  limitValue: number | null;
}

/** This period's metered usage per metric, with the plan's cap where one exists. */
export async function getBillingUsage(getToken: TokenProvider, signal?: AbortSignal): Promise<BillingUsage[]> {
  return (await apiFetch<{ items: BillingUsage[] }>("/api/v1/billing/usage", { getToken, signal })).items;
}
