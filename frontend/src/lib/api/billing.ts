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
