"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { SignOutButton } from "@clerk/nextjs";
import { useTranslations } from "next-intl";
import { updateMe, type ProfileUpdate } from "@/lib/api/auth";
import { ApiError } from "@/lib/api/client";
import { useTokenProvider } from "@/lib/api/use-token-provider";
import { useProvisionGate } from "@/components/auth/provision-gate";
import { BrandMark } from "@/components/ui/brand-mark";

/**
 * First-run capture of the professional details Draftly prints on forms.
 *
 * Reached only via the provisioning gate, which sends a user here when
 * `needsOnboarding()` is true — that is, when `notaryRegistration` or
 * `jurisdiction` is null. First-login provisioning leaves both null and
 * defaults `displayName` to the verified email, so every new account lands
 * here exactly once.
 *
 * Deliberately outside `AppShell`: this is a first-run flow, not a settings
 * page, and the workspace chrome would offer navigation away from a step the
 * gate is going to send them back to.
 */

/** Every field `UpdateProfileRequest` accepts. It sets `extra="forbid"`. */
interface OnboardingDraft {
  displayName: string;
  professionalTitles: string;
  qualifications: string;
  notaryRegistration: string;
  jurisdiction: string;
  addressLine1: string;
  addressLine2: string;
  phone: string;
}

const EMPTY: OnboardingDraft = {
  displayName: "",
  professionalTitles: "",
  qualifications: "",
  notaryRegistration: "",
  jurisdiction: "",
  addressLine1: "",
  addressLine2: "",
  phone: "",
};

/**
 * Only non-empty values are sent. A blank optional field must stay null in the
 * database rather than becoming an empty string, so "not provided" and
 * "provided as blank" do not collapse into the same value.
 */
function toProfileUpdate(draft: OnboardingDraft): ProfileUpdate {
  const update: ProfileUpdate = {};
  for (const [key, value] of Object.entries(draft) as [keyof OnboardingDraft, string][]) {
    const trimmed = value.trim();
    if (trimmed) update[key] = trimmed;
  }
  return update;
}

function TextField({
  label,
  mark,
  value,
  onChange,
  multiline,
}: {
  label: string;
  mark: string;
  value: string;
  onChange: (value: string) => void;
  multiline?: boolean;
}) {
  const shared =
    "border-border-control focus-visible:outline-ring bg-surface mt-1 w-full rounded-control border px-3 py-2 text-sm";
  return (
    <label className="block">
      <span className="flex items-baseline justify-between gap-2">
        <span className="text-muted-ink text-xs">{label}</span>
        <span className="text-muted-ink text-xs">{mark}</span>
      </span>
      {multiline ? (
        <textarea
          className={shared}
          rows={2}
          value={value}
          onChange={(e) => onChange(e.target.value)}
        />
      ) : (
        <input className={shared} value={value} onChange={(e) => onChange(e.target.value)} />
      )}
    </label>
  );
}

export function OnboardingScreen() {
  const t = useTranslations("onboarding");
  const tProfile = useTranslations("profile");
  const router = useRouter();
  const getToken = useTokenProvider();
  const { refreshProvisioning } = useProvisionGate();

  const [draft, setDraft] = useState<OnboardingDraft>(EMPTY);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const required = t("requiredMark");
  const optional = t("optionalMark");

  // Mirrors `needsOnboarding()`: submitting without these would land the user
  // straight back here via the gate, which reads as the button being broken.
  const canSubmit =
    draft.notaryRegistration.trim().length > 0 && draft.jurisdiction.trim().length > 0;

  function set<K extends keyof OnboardingDraft>(key: K) {
    return (value: string) => setDraft((d) => ({ ...d, [key]: value }));
  }

  async function submit() {
    if (!canSubmit) {
      setError(t("missingRequired"));
      return;
    }
    setSaving(true);
    setError(null);
    try {
      await updateMe(getToken, toProfileUpdate(draft));
      // Clears the gate's cached "needs onboarding" outcome so it re-fetches
      // instead of reading the stale value and bouncing this user straight
      // back here once `/` renders.
      refreshProvisioning();
      // `replace`, not `push`: onboarding is complete, so Back must not return
      // to a form the gate would immediately redirect away from again.
      router.replace("/");
    } catch (caught: unknown) {
      if (caught instanceof ApiError) {
        console.error(
          `Onboarding save failed (${caught.code}, correlation ${caught.correlationId}): ${caught.message}`,
        );
      } else {
        console.error("Onboarding save failed:", caught);
      }
      setError(t("saveFailed"));
      setSaving(false);
    }
  }

  return (
    <main className="bg-canvas flex min-h-screen flex-col items-center px-4 py-12">
      <div className="w-full max-w-2xl">
        <BrandMark className="mb-4 size-12" priority />
        <h1 className="font-heading text-ink text-3xl font-semibold tracking-tight">
          {t("title")}
        </h1>
        <p className="text-muted-ink mt-2 text-sm">{t("description")}</p>
        <p className="text-muted-ink mt-1 text-sm">{t("requiredNote")}</p>

        <form
          className="mt-8 space-y-8"
          onSubmit={(e) => {
            e.preventDefault();
            void submit();
          }}
        >
          <section>
            <h2 className="text-lg font-semibold">{tProfile("identity")}</h2>
            <div className="mt-3 grid gap-4 sm:grid-cols-2">
              <TextField
                label={tProfile("nameLabel")}
                mark={optional}
                value={draft.displayName}
                onChange={set("displayName")}
              />
            </div>
          </section>

          <section>
            <h2 className="text-lg font-semibold">{tProfile("practice")}</h2>
            <div className="mt-3 grid gap-4 sm:grid-cols-2">
              <TextField
                label={tProfile("notaryCodeLabel")}
                mark={required}
                value={draft.notaryRegistration}
                onChange={set("notaryRegistration")}
              />
              <TextField
                label={tProfile("jurisdictionLabel")}
                mark={required}
                value={draft.jurisdiction}
                onChange={set("jurisdiction")}
              />
              <TextField
                label={tProfile("titlesLabel")}
                mark={optional}
                value={draft.professionalTitles}
                onChange={set("professionalTitles")}
              />
              <TextField
                label={tProfile("qualificationsLabel")}
                mark={optional}
                value={draft.qualifications}
                onChange={set("qualifications")}
                multiline
              />
            </div>
          </section>

          <section>
            <h2 className="text-lg font-semibold">{tProfile("contact")}</h2>
            <div className="mt-3 grid gap-4 sm:grid-cols-2">
              <TextField
                label={tProfile("addressLine1Label")}
                mark={optional}
                value={draft.addressLine1}
                onChange={set("addressLine1")}
              />
              <TextField
                label={tProfile("addressLine2Label")}
                mark={optional}
                value={draft.addressLine2}
                onChange={set("addressLine2")}
              />
              <TextField
                label={tProfile("phoneLabel")}
                mark={optional}
                value={draft.phone}
                onChange={set("phone")}
              />
            </div>
          </section>

          {error && (
            <p role="alert" className="text-red text-sm">
              {error}
            </p>
          )}

          <div className="border-border flex flex-wrap items-center gap-3 border-t pt-5">
            <button
              type="submit"
              disabled={saving || !canSubmit}
              className="bg-forest hover:bg-forest/90 focus-visible:outline-ring rounded-control px-4 py-2 text-sm text-white disabled:cursor-not-allowed disabled:opacity-50"
            >
              {saving ? t("submitting") : t("submit")}
            </button>
            <SignOutButton redirectUrl="/sign-in">
              <button
                type="button"
                className="border-border hover:bg-hover-bg focus-visible:outline-ring rounded-control border px-3 py-2 text-sm"
              >
                {t("signOut")}
              </button>
            </SignOutButton>
          </div>
        </form>
      </div>
    </main>
  );
}
