import { redirect } from "next/navigation";
import { OnboardingScreen } from "@/components/auth/onboarding-screen";
import { isClerkConfigured } from "@/lib/auth/clerk";
import { isApiEnabled } from "@/lib/api/client";

export default function OnboardingPage() {
  // `OnboardingScreen` calls `useTokenProvider()` -> Clerk's `useAuth()`,
  // which throws without a `ClerkProvider` in the tree. The offline demo
  // (reachable today via `AUTH_BYPASS=true`) runs without one and without a
  // provisioning gate to send anyone here, so this route has to guard itself.
  if (!isClerkConfigured() || !isApiEnabled()) {
    redirect("/");
  }

  return <OnboardingScreen />;
}
