import type { SignIn } from "@clerk/nextjs";
import type { ComponentProps } from "react";

type Appearance = NonNullable<ComponentProps<typeof SignIn>["appearance"]>;

// tailwind.config.ts radii (rounded-control, rounded-card). They are Tailwind
// tokens, not CSS variables, so Clerk's style objects take the values.
const RADIUS_CONTROL = "9999px";
const RADIUS_CARD = "16px";

/**
 * Draftly's look for Clerk's sign-in and sign-up, written once and used by both.
 *
 * Every colour is a design token (globals.css), never a literal, so the auth
 * screens and the workspace cannot drift apart. Clerk injects its own styles
 * after ours, so overrides are style objects, which it merges last, not class
 * names, which lose the cascade.
 *
 * Do not hide Clerk's "Development mode" notice here: it comes from development
 * keys and disappears on its own with production keys.
 */
const FONT = "var(--font-plex), var(--font-noto-sans-si), sans-serif";

const control = {
  minHeight: "2.5rem",
  borderRadius: RADIUS_CONTROL,
  fontSize: "0.875rem",
} as const;

export const draftlyAppearance: Appearance = {
  options: {
    socialButtonsPlacement: "top",
    socialButtonsVariant: "blockButton",
  },
  variables: {
    // Navy, not gold: this colour also drives links and Clerk's own focus ring.
    colorPrimary: "var(--forest)",
    colorPrimaryForeground: "#ffffff",
    colorForeground: "var(--ink)",
    colorMutedForeground: "var(--muted-ink)",
    colorMuted: "var(--canvas)",
    colorBackground: "var(--surface)",
    colorInput: "var(--surface)",
    colorInputForeground: "var(--ink)",
    colorBorder: "var(--border)",
    colorRing: "var(--ring)",
    colorDanger: "var(--red)",
    colorSuccess: "var(--success)",
    colorWarning: "var(--amber-text)",
    fontFamily: FONT,
    fontFamilyButtons: FONT,
  },
  elements: {
    rootBox: { width: "100%" },
    cardBox: { width: "100%", boxShadow: "none", border: "none", borderRadius: RADIUS_CARD },
    card: {
      width: "100%",
      boxShadow: "none",
      border: "1px solid var(--border) !important",
      borderRadius: RADIUS_CARD,
      padding: "2rem",
      gap: "1.5rem",
    },
    headerTitle: { fontFamily: FONT, fontSize: "1.25rem", fontWeight: 600, color: "var(--ink)" },
    headerSubtitle: { fontSize: "0.875rem", color: "var(--muted-ink)" },
    // The primary action, in the shared primary style (see Button): a vertical gold gradient, a 1px
    // border and a top highlight, navy ink (white on gold is 2.7:1). Clerk cannot fade a gradient,
    // so its hover swaps to the lighter gradient at once.
    formButtonPrimary: {
      ...control,
      backgroundColor: "var(--primary-pressed) !important",
      backgroundImage: "linear-gradient(to bottom, var(--primary-top), var(--primary-bottom)) !important",
      border: "1px solid var(--primary-border) !important",
      color: "var(--primary-ink) !important",
      fontWeight: 600,
      boxShadow: "var(--primary-highlight) !important",
      "&::before, &::after": { display: "none" },
      "&:hover": { backgroundImage: "linear-gradient(to bottom, var(--primary-hover-top), var(--primary-hover-bottom)) !important" },
      "&:active": { backgroundImage: "none !important", boxShadow: "none !important" },
      "&:focus-visible": { outline: "2px solid var(--ring)", outlineOffset: "2px" },
    },
    // Provider buttons: quiet secondary actions, one height, a visible focus ring.
    socialButtons: { gridTemplateColumns: "1fr" },
    socialButtonsBlockButton: {
      ...control,
      backgroundColor: "var(--surface) !important",
      border: "1px solid var(--border-strong) !important",
      color: "var(--ink)",
      fontWeight: 500,
      boxShadow: "none !important",
      "&:hover": { backgroundColor: "var(--hover-bg) !important" },
      "&:focus-visible": { outline: "2px solid var(--ring)", outlineOffset: "2px" },
    },
    socialButtonsBlockButtonText: { fontWeight: 500 },
    dividerLine: { backgroundColor: "var(--border)" },
    dividerText: { color: "var(--muted-ink)", fontSize: "0.875rem" },
    formFieldLabel: { color: "var(--ink)", fontSize: "0.875rem", fontWeight: 500 },
    formFieldInput: {
      ...control,
      border: "1px solid var(--border-control) !important",
      backgroundColor: "var(--surface)",
      color: "var(--ink)",
      boxShadow: "none !important",
      "&:focus": { outline: "2px solid var(--ring)", outlineOffset: "2px", boxShadow: "none !important" },
    },
    otpCodeFieldInput: {
      border: "1px solid var(--border-control) !important",
      boxShadow: "none !important",
      borderRadius: RADIUS_CONTROL,
      textAlign: "center",
      fontVariantNumeric: "tabular-nums",
    },
    formFieldErrorText: { color: "var(--red)", fontSize: "0.875rem" },
    formFieldHintText: { color: "var(--muted-ink)", fontSize: "0.8125rem" },
    footerActionText: { color: "var(--muted-ink)", fontSize: "0.875rem" },
    footerActionLink: { color: "var(--forest)", fontWeight: 500, "&:hover": { textDecoration: "underline" } },
    identityPreviewText: { color: "var(--ink)", fontSize: "0.875rem" },
    // Clerk's required footer stays, small and muted, inside the same card.
    footer: { backgroundColor: "var(--canvas)" },
  },
};
