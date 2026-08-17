import { describe, expect, it } from "vitest";
import { decideGate, ONBOARDING_PATH } from "./provision-decision";

describe("decideGate", () => {
  it("renders children when outcome is ready, regardless of pathname", () => {
    expect(decideGate({ outcome: "ready", pathname: "/" })).toEqual({ render: "children" });
    expect(decideGate({ outcome: "ready", pathname: "/matters/abc" })).toEqual({
      render: "children",
    });
    expect(decideGate({ outcome: "ready", pathname: ONBOARDING_PATH })).toEqual({
      render: "children",
    });
  });

  it("renders children on the onboarding path when outcome is needs-onboarding, so the onboarding page can paint instead of leaving the user stuck on a blank screen forever", () => {
    expect(decideGate({ outcome: "needs-onboarding", pathname: ONBOARDING_PATH })).toEqual({
      render: "children",
    });
  });

  it("blocks and redirects to the onboarding path when outcome is needs-onboarding and pathname is not exactly the onboarding path", () => {
    expect(decideGate({ outcome: "needs-onboarding", pathname: "/" })).toEqual({
      render: "blocking",
      redirectTo: ONBOARDING_PATH,
    });
    expect(decideGate({ outcome: "needs-onboarding", pathname: "/matters/abc" })).toEqual({
      render: "blocking",
      redirectTo: ONBOARDING_PATH,
    });
    // "/onboarding/extra" is not a strict equal match for ONBOARDING_PATH
    // (decideGate compares with `===`, not a prefix check), so it is treated
    // like any other non-onboarding route: blocked and redirected back to
    // the exact onboarding path.
    expect(decideGate({ outcome: "needs-onboarding", pathname: "/onboarding/extra" })).toEqual({
      render: "blocking",
      redirectTo: ONBOARDING_PATH,
    });
  });

  it("blocks without a redirect target when outcome is unknown", () => {
    const decision = decideGate({ outcome: "unknown", pathname: "/" });
    expect(decision).toEqual({ render: "blocking" });
    expect(decision).not.toHaveProperty("redirectTo");
  });

  it("renders the error state when outcome is failed", () => {
    expect(decideGate({ outcome: "failed", pathname: "/" })).toEqual({ render: "error" });
  });
});
