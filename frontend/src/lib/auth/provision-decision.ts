/**
 * Pure decision logic for `ProvisionGate`.
 *
 * Kept free of React and `next/navigation` so the gate/redirect rules can be
 * exercised as plain data-in/data-out — no DOM, no router, no effects.
 */

/** Where provisioning currently stands for the signed-in user. */
export type ProvisionOutcome = "unknown" | "ready" | "needs-onboarding" | "failed";

/** The one route allowed to render while `needsOnboarding` is true. */
export const ONBOARDING_PATH = "/onboarding";

export type GateDecision =
  | { render: "children" }
  | { render: "blocking"; redirectTo?: string }
  | { render: "error" };

/**
 * Decide what the gate should render for a given provisioning outcome and
 * current path.
 *
 * The `needs-onboarding` + already-on-`/onboarding` case is the one that
 * matters: without it, the gate would redirect to `/onboarding` and then,
 * on the very next render (same outcome, new pathname), redirect again
 * forever, since nothing about the outcome changes just because the URL
 * did. Letting the onboarding page itself render children out of a
 * `needs-onboarding` outcome is what lets the redirect ever resolve.
 */
export function decideGate(input: {
  outcome: ProvisionOutcome;
  pathname: string;
}): GateDecision {
  const { outcome, pathname } = input;

  switch (outcome) {
    case "ready":
      return { render: "children" };
    case "needs-onboarding":
      return pathname === ONBOARDING_PATH
        ? { render: "children" }
        : { render: "blocking", redirectTo: ONBOARDING_PATH };
    case "failed":
      return { render: "error" };
    case "unknown":
      return { render: "blocking" };
  }
}
