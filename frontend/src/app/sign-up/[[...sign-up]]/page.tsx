import { SignUp } from "@clerk/nextjs";
import { getTranslations } from "next-intl/server";
import { redirect } from "next/navigation";
import { GavelAnimation } from "@/components/auth/gavel-animation";
import { BrandMark } from "@/components/ui/brand-mark";
import { isClerkConfigured } from "@/lib/auth/clerk";

export default async function SignUpPage() {
  if (!isClerkConfigured()) {
    redirect("/");
  }

  const t = await getTranslations("auth");

  return (
    <main className="bg-canvas min-h-screen lg:grid lg:grid-cols-2">
      <div className="flex min-h-screen flex-col items-center justify-center px-4 py-8 sm:px-8 lg:px-10">
        <div className="mb-8 flex flex-col items-center text-center">
          <BrandMark className="mb-4 size-14" priority />
          <h1 className="font-heading text-ink text-3xl font-semibold tracking-tight">
            {t("signUpTitle")}
          </h1>
          <p className="text-muted-ink mt-2 max-w-sm text-sm">
            {t("signUpBody")}
          </p>
        </div>
        <SignUp
          routing="hash"
          forceRedirectUrl="/"
          // Keeps the footer "Sign in" link inside the app rather than sending
          // the user to Clerk's unstyled hosted Account Portal.
          signInUrl="/sign-in"
          appearance={{
            elements: {
              rootBox: "mx-auto",
              card: "shadow-none border border-border rounded-dialog font-ui",
              headerTitle: "font-heading text-ink font-semibold",
              headerSubtitle: "text-muted-ink",
              formButtonPrimary:
                "bg-forest hover:bg-forest/90 focus-visible:outline-ring rounded-control text-sm font-medium text-white",
              formFieldInput:
                "border-border focus-visible:outline-ring rounded-control bg-surface text-sm",
              footerActionLink: "text-forest hover:text-forest/80",
              socialButtonsBlockButton:
                "border-border rounded-control hover:bg-hover-bg text-sm font-medium",
              identityPreviewText: "text-ink text-sm",
              otpCodeFieldInput:
                "border-border focus-visible:outline-ring rounded-control text-center font-ui tabular-nums",
            },
          }}
        />
      </div>
      <aside
        aria-hidden="true"
        className="bg-ink hidden min-h-screen items-center justify-center overflow-hidden px-8 lg:flex"
      >
        <GavelAnimation />
      </aside>
    </main>
  );
}
