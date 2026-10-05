import { SignIn } from "@clerk/nextjs";
import { redirect } from "next/navigation";
import { AuthShell } from "@/components/auth/auth-shell";
import { draftlyAppearance } from "@/lib/auth/clerk-appearance";
import { isClerkConfigured } from "@/lib/auth/clerk";

export default async function SignInPage() {
  if (!isClerkConfigured()) {
    redirect("/");
  }

  return (
    <AuthShell>
      <SignIn
        routing="hash"
        forceRedirectUrl="/"
        // Without this, the footer "Sign up" link falls back to Clerk's hosted
        // Account Portal, which cannot see the appearance overrides.
        signUpUrl="/sign-up"
        appearance={draftlyAppearance}
      />
    </AuthShell>
  );
}
