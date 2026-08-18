"use client";

import { createContext, useContext, useEffect, useRef, useState } from "react";
import { usePathname, useRouter } from "next/navigation";
import { useAuth } from "@clerk/nextjs";
import { useTranslations } from "next-intl";
import { needsOnboarding, provisionMe } from "@/lib/api/auth";
import { ApiError, isApiEnabled } from "@/lib/api/client";
import { useTokenProvider } from "@/lib/api/use-token-provider";
import { decideGate, type ProvisionOutcome } from "@/lib/auth/provision-decision";

/**
 * Links the signed-in Clerk identity to a Draftly user, and sends first-time
 * users to onboarding.
 *
 * Clerk authenticates entirely against its own servers, so a successful
 * sign-in tells our backend nothing. Without this, `users` and
 * `user_identities` stay empty and every authenticated route answers
 * `account_pending` — the account exists to Clerk and does not exist to
 * Draftly.
 *
 * This *gates* rather than fires-and-forgets: children are withheld until
 * provisioning resolves. Two reasons. A screen that calls an authenticated
 * route during its first render would otherwise race provisioning and get
 * `account_pending`. And the onboarding redirect has to happen before the
 * workspace paints, or the user sees a flash of a workspace they are about to
 * be pulled out of.
 *
 * Mounted in the root layout rather than on one page because the sign-in flow
 * can land anywhere: `forceRedirectUrl="/"` today, but a deep link the user
 * was bounced off returns them there instead.
 */
export function ProvisionGate({ children }: { children: React.ReactNode }) {
  // `useTokenProvider` calls Clerk's `useAuth`, which needs a `ClerkProvider`.
  // The offline demo runs without one, so the hook lives in a child that is
  // only mounted when the backend is configured. `isApiEnabled()` reads an
  // inlined build-time env var, so this branch never changes between renders
  // and hook order stays stable.
  return isApiEnabled() ? <ApiBoundProvisionGate>{children}</ApiBoundProvisionGate> : children;
}

interface ProvisionGateContextValue {
  /**
   * Clear the cached provisioning outcome and refetch it. Onboarding calls
   * this right after saving, so the gate learns `needsOnboarding` has flipped
   * to false before it re-evaluates the redirect — without it, the cached
   * "needs onboarding" outcome would bounce the user straight back to
   * `/onboarding` after every save.
   */
  refreshProvisioning: () => void;
}

// No-op default: the demo-mode `ProvisionGate` passthrough never mounts
// `ApiBoundProvisionGate`, so consumers of this context outside the API-bound
// tree (or in tests) get a harmless function instead of `undefined`.
const ProvisionGateContext = createContext<ProvisionGateContextValue>({
  refreshProvisioning: () => {},
});

export function useProvisionGate(): ProvisionGateContextValue {
  return useContext(ProvisionGateContext);
}

const RETRY_DELAY_MS = 800;

function ApiBoundProvisionGate({ children }: { children: React.ReactNode }) {
  const { isLoaded, isSignedIn } = useAuth();
  const getToken = useTokenProvider();
  const router = useRouter();
  const pathname = usePathname();
  const t = useTranslations("app");
  const [outcome, setOutcome] = useState<ProvisionOutcome>("unknown");
  // Provisioning is idempotent server-side, so a duplicate call is harmless —
  // this only avoids the pointless second request React's StrictMode would
  // otherwise fire in development.
  const attempted = useRef(false);
  // One automatic retry before surfacing a blocking error, so a transient
  // network blip doesn't require the user to notice and click anything.
  const hasRetried = useRef(false);
  // Bumping this re-runs the effect below without adding `outcome` itself to
  // the dependency array (which would also re-run on every unrelated outcome
  // change, e.g. once the redirect-in-flight case resolves).
  const [retryTick, setRetryTick] = useState(0);

  useEffect(() => {
    if (!isLoaded) return;

    // Signed out: the middleware owns that redirect, and the sign-in and
    // sign-up pages are public. Nothing to provision, so never block.
    //
    // Reset the attempt guards here too: without this, signing out and back
    // into a different account in the same tab would skip provisioning and
    // the onboarding check entirely, since `attempted` would still be true
    // from the previous session.
    if (!isSignedIn) {
      attempted.current = false;
      hasRetried.current = false;
      setOutcome("ready");
      return;
    }

    if (attempted.current) return;
    attempted.current = true;
    // Signing in inside a tab that was signed out leaves `outcome` at "ready"
    // from the branch above. Blocking again while this fetch is in flight is
    // what stops the workspace painting for the moment before we know whether
    // the user is headed to onboarding. A no-op on first mount.
    setOutcome("unknown");

    let cancelled = false;
    let retryTimer: ReturnType<typeof setTimeout> | undefined;

    void provisionMe(getToken)
      .then((user) => {
        if (cancelled) return;
        setOutcome(needsOnboarding(user) ? "needs-onboarding" : "ready");
      })
      .catch((error: unknown) => {
        if (error instanceof ApiError) {
          console.error(
            `Draftly provisioning failed (${error.code}, correlation ${error.correlationId}): ${error.message}`,
          );
        } else {
          console.error("Draftly provisioning failed:", error);
        }
        if (cancelled) return;

        // A failure here leaves the user signed in to Clerk with no known
        // Draftly profile state — admitting them anyway would risk showing
        // (or letting them past) a stale/blank profile, which is exactly
        // what this gate exists to prevent. Retry once, then block.
        if (!hasRetried.current) {
          hasRetried.current = true;
          attempted.current = false;
          retryTimer = setTimeout(() => {
            if (!cancelled) setRetryTick((n) => n + 1);
          }, RETRY_DELAY_MS);
        } else {
          setOutcome("failed");
        }
      });

    return () => {
      cancelled = true;
      if (retryTimer) clearTimeout(retryTimer);
    };
  }, [isLoaded, isSignedIn, getToken, retryTick]);

  const decision = decideGate({ outcome, pathname });
  const redirectTo = decision.render === "blocking" ? decision.redirectTo : undefined;

  // Separate from the provisioning fetch: this reruns whenever the outcome or
  // the pathname changes, so a `needs-onboarding` outcome that is still true
  // after the pathname updates to `/onboarding` stops redirecting instead of
  // looping.
  useEffect(() => {
    if (redirectTo) router.replace(redirectTo);
  }, [redirectTo, router]);

  function refreshProvisioning() {
    hasRetried.current = false;
    attempted.current = false;
    setOutcome("unknown");
    setRetryTick((n) => n + 1);
  }

  let body: React.ReactNode;
  if (decision.render === "children") {
    body = children;
  } else if (decision.render === "error") {
    body = (
      <div className="bg-canvas grid min-h-screen place-items-center p-8 text-center">
        <div>
          <h1 className="font-heading text-ink text-xl font-semibold">{t("errorTitle")}</h1>
          <p className="text-muted-ink mt-2 text-sm">{t("errorBody")}</p>
          <button
            type="button"
            className="bg-forest hover:bg-forest/90 focus-visible:outline-ring mt-4 rounded-[6px] px-4 py-2 text-sm text-white"
            onClick={refreshProvisioning}
          >
            {t("retry")}
          </button>
        </div>
      </div>
    );
  } else {
    // Intentionally bare: this is a sub-second gap in the common case, and a
    // spinner that flashes for 200ms reads as jank rather than as progress.
    body = <div aria-busy="true" className="bg-canvas min-h-screen" />;
  }

  return (
    <ProvisionGateContext.Provider value={{ refreshProvisioning }}>
      {body}
    </ProvisionGateContext.Provider>
  );
}
