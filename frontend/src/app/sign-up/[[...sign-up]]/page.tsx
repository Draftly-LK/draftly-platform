import { SignUp } from "@clerk/nextjs";
import { getTranslations } from "next-intl/server";
import { redirect } from "next/navigation";
import { isClerkConfigured } from "@/lib/auth/clerk";

export default async function SignUpPage() {
  if (!isClerkConfigured()) {
    redirect("/");
  }

  const t = await getTranslations("auth");

  return (
    <main className="bg-canvas flex min-h-screen flex-col items-center justify-center px-4 py-4">
      <div className="mb-8 text-center">
        <h1 className="font-heading text-ink text-3xl font-semibold tracking-tight">
          {t("signUpTitle")}
        </h1>
        <p className="text-muted-ink mt-2 max-w-sm text-sm">{t("signUpBody")}</p>
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
            card: "shadow-none border border-border rounded-[8px] font-ui",
            headerTitle: "font-heading text-ink font-semibold",
            headerSubtitle: "text-muted-ink",
            formButtonPrimary:
              "bg-forest hover:bg-forest/90 focus-visible:outline-ring rounded-[6px] text-sm font-medium text-white",
            formFieldInput:
              "border-border focus-visible:outline-ring rounded-[6px] bg-surface text-sm",
            footerActionLink: "text-forest hover:text-forest/80",
            socialButtonsBlockButton:
              "border-border rounded-[6px] hover:bg-hover-bg text-sm font-medium",
            identityPreviewText: "text-ink text-sm",
            otpCodeFieldInput:
              "border-border focus-visible:outline-ring rounded-[6px] text-center font-ui tabular-nums",
          },
        }}
      />
    </main>
  );
}
