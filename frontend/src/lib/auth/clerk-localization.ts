import type { ClerkProvider } from "@clerk/nextjs";
import type { ComponentProps } from "react";

type Localization = NonNullable<ComponentProps<typeof ClerkProvider>["localization"]>;

interface AuthCopy {
  (key: "signInTitle" | "signInBody" | "signUpTitle" | "signUpBody" | "or"): string;
  (key: "continueWith", values: { provider: string }): string;
}

// Clerk's own placeholder syntax, handed through the message untouched.
const PROVIDER = "{{provider|titleize}}";

/**
 * The few strings the auth screens say in Draftly's voice: the start-screen
 * titles, the "or" divider and "Continue with Google". Everything else (error
 * messages, verification steps) stays Clerk's.
 */
export function draftlyClerkLocalization(t: AuthCopy): Localization {
  const continueWith = t("continueWith", { provider: PROVIDER });
  return {
    signIn: { start: { title: t("signInTitle"), subtitle: t("signInBody") } },
    signUp: { start: { title: t("signUpTitle"), subtitle: t("signUpBody") } },
    socialButtonsBlockButton: continueWith,
    socialButtonsBlockButtonManyInView: continueWith,
    dividerText: t("or"),
  };
}
