import { SignUp } from "@clerk/nextjs";
import { redirect } from "next/navigation";
import { AuthShell } from "@/components/auth/auth-shell";
import { draftlyAppearance } from "@/lib/auth/clerk-appearance";
import { isClerkConfigured } from "@/lib/auth/clerk";

export default async function SignUpPage() {
  if (!isClerkConfigured()) {
    redirect("/");
  }

  return (
    <AuthShell>
      <SignUp
        routing="hash"
        forceRedirectUrl="/"
        // Keeps the footer "Sign in" link inside the app rather than sending
        // the user to Clerk's unstyled hosted Account Portal.
        signInUrl="/sign-in"
        appearance={draftlyAppearance}
      />
    </AuthShell>
  );
}
