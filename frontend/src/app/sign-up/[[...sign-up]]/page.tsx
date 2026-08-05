import { SignUp } from "@clerk/nextjs";
import { getTranslations } from "next-intl/server";
import { redirect } from "next/navigation";
import { hasClerkPublishableKey } from "@/lib/auth/clerk";

export default async function SignUpPage() {
  if (!hasClerkPublishableKey()) {
    redirect("/");
  }

  const t = await getTranslations("auth");

  return (
    <main className="bg-canvas flex min-h-screen flex-col items-center justify-center px-4 py-12">
      <div className="mb-8 text-center">
        <h1 className="font-heading text-ink text-3xl font-semibold tracking-tight">
          {t("signUpTitle")}
        </h1>
        <p className="text-muted-ink mt-2 max-w-sm text-sm">{t("signUpBody")}</p>
      </div>
      <SignUp
        forceRedirectUrl="/"
        appearance={{
          elements: {
            rootBox: "mx-auto",
            card: "shadow-none border border-border rounded-[8px]",
          },
        }}
      />
    </main>
  );
}
