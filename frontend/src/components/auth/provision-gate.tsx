"use client";

import { useEffect, useRef, useState } from "react";
import { usePathname, useRouter } from "next/navigation";
import { useAuth } from "@clerk/nextjs";
import { needsOnboarding, provisionMe } from "@/lib/api/auth";
import { ApiError, isApiEnabled } from "@/lib/api/client";
import { useTokenProvider } from "@/lib/api/use-token-provider";

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

type Status = "waiting" | "provisioning" | "ready";

function ApiBoundProvisionGate({ children }: { children: React.ReactNode }) {
  const { isLoaded, isSignedIn } = useAuth();
  const getToken = useTokenProvider();
  const router = useRouter();
  const pathname = usePathname();
  const [status, setStatus] = useState<Status>("waiting");
  // Provisioning is idempotent server-side, so a duplicate call is harmless —
  // this only avoids the pointless second request React's StrictMode would
  // otherwise fire in development.
  const attempted = useRef(false);

  useEffect(() => {
    if (!isLoaded) return;

    // Signed out: the middleware owns that redirect, and the sign-in and
    // sign-up pages are public. Nothing to provision, so never block.
    if (!isSignedIn) {
      setStatus("ready");
      return;
    }

    if (attempted.current) return;
    attempted.current = true;
    setStatus("provisioning");

    void provisionMe(getToken)
      .then((user) => {
        if (needsOnboarding(user) && pathname !== "/onboarding") {
          router.replace("/onboarding");
          // Deliberately not marking ready: the redirect is in flight, and
          // revealing the workspace first is the flash this gate prevents.
          return;
        }
        setStatus("ready");
      })
      .catch((error: unknown) => {
        // A failure here leaves the user signed in to Clerk with no Draftly
        // row, which authenticated routes already report as `account_pending`.
        // Render anyway rather than trapping them behind a blank gate — the
        // screens surface that state, and a reload retries provisioning.
        if (error instanceof ApiError) {
          console.error(
            `Draftly provisioning failed (${error.code}, correlation ${error.correlationId}): ${error.message}`,
          );
        } else {
          console.error("Draftly provisioning failed:", error);
        }
        setStatus("ready");
      });
  }, [isLoaded, isSignedIn, getToken, router, pathname]);

  if (status === "ready") return children;

  // Intentionally bare: this is a sub-second gap in the common case, and a
  // spinner that flashes for 200ms reads as jank rather than as progress.
  return <div aria-busy="true" className="bg-canvas min-h-screen" />;
}
