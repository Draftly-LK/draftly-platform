import { describe, expect, it } from "vitest";
import { draftlyAppearance } from "./clerk-appearance";
import { draftlyClerkLocalization } from "./clerk-localization";

describe("draftlyAppearance", () => {
  const json = JSON.stringify(draftlyAppearance);

  it("draws every colour from design tokens, so auth and workspace cannot drift", () => {
    const literalColours = json.match(/#[0-9a-fA-F]{3,8}\b/g) ?? [];
    // White on the navy primary-foreground is the only literal; everything else is a var().
    expect(literalColours).toEqual(["#ffffff"]);
    expect(json).toContain("var(--forest)");
    expect(json).toContain("var(--ring)");
  });

  it("has no purple anywhere", () => {
    expect(json.toLowerCase()).not.toMatch(/purple|violet|#6c47ff|#7c3aed/);
  });

  it("makes the primary button gold with navy text, never white on gold", () => {
    const primary = JSON.stringify((draftlyAppearance.elements as Record<string, unknown>).formButtonPrimary);
    expect(primary).toContain("var(--gold)");
    expect(primary).toContain("var(--navy-950)");
    expect(primary).not.toContain("#fff");
  });

  it("gives inputs the 3:1 boundary token and the navy focus ring", () => {
    const input = JSON.stringify((draftlyAppearance.elements as Record<string, unknown>).formFieldInput);
    expect(input).toContain("var(--border-control)");
    expect(input).toContain("var(--ring)");
  });

  it("never hides Clerk's development-mode notice or its branding", () => {
    expect(json).not.toMatch(/"footer(Pages|Action)?"?:\{[^}]*display:"none"/);
    expect(json).not.toContain("logoBox");
  });
});

describe("draftlyClerkLocalization", () => {
  const t = ((key: string, values?: { provider: string }) =>
    values ? `${key}:${values.provider}` : key) as Parameters<typeof draftlyClerkLocalization>[0];

  it("passes Clerk's provider placeholder through untouched", () => {
    const loc = draftlyClerkLocalization(t);
    expect(loc.socialButtonsBlockButton).toBe("continueWith:{{provider|titleize}}");
    expect(loc.socialButtonsBlockButtonManyInView).toBe("continueWith:{{provider|titleize}}");
  });

  it("titles both start screens in Draftly's voice", () => {
    const loc = draftlyClerkLocalization(t);
    expect(loc.signIn?.start?.title).toBe("signInTitle");
    expect(loc.signUp?.start?.title).toBe("signUpTitle");
    expect(loc.dividerText).toBe("or");
  });
});
