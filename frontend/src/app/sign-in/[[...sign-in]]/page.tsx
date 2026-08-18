import { SignIn } from "@clerk/nextjs";
import { getTranslations } from "next-intl/server";
import { redirect } from "next/navigation";
import { isClerkConfigured } from "@/lib/auth/clerk";

export default async function SignInPage() {
  if (!isClerkConfigured()) {
    redirect("/");
  }

  const t = await getTranslations("auth");

  return (
    <main className="bg-canvas flex min-h-screen flex-col items-center justify-center px-4 py-12">
      <div className="mb-8 text-center">
        <h1 className="font-heading text-ink text-3xl font-semibold tracking-tight">
          {t("signInTitle")}
        </h1>
        <p className="text-muted-ink mt-2 max-w-sm text-sm">{t("signInBody")}</p>
      </div>
      <SignIn
        routing="hash"
        forceRedirectUrl="/"
        // Without this, the footer "Sign up" link falls back to Clerk's hosted
        // Account Portal, which cannot see the appearance overrides below.
        signUpUrl="/sign-up"
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
