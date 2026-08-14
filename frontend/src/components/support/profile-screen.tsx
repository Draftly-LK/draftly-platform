"use client";

import { useRef, useState, type ChangeEvent } from "react";
import Link from "next/link";
import { SignOutButton, useUser } from "@clerk/nextjs";
import { useTranslations } from "next-intl";
import { AppShell } from "@/components/shell/app-shell";
import { PageHeader } from "@/components/shell/page-header";
import { useDemoStore } from "@/lib/store";
import type { User } from "@/types";

function getInitials(name: string): string {
  return name
    .split(" ")
    .filter(Boolean)
    .slice(0, 2)
    .map((w) => w[0]?.toUpperCase() ?? "")
    .join("");
}

/** Fields Draftly owns — not available from Clerk/email auth. */
type EditableProfile = Pick<
  User,
  | "qualifications"
  | "professionalTitles"
  | "notaryRegistration"
  | "jurisdiction"
  | "addressLine1"
  | "addressLine2"
  | "phone"
>;

function displayOrDash(value: string): string {
  const trimmed = value.trim();
  return trimmed.length > 0 ? trimmed : "—";
}

function ProfilePhoto({
  name,
  imageUrl,
  onUpload,
  uploading,
  canUpload,
}: {
  name: string;
  imageUrl: string | null;
  onUpload: (file: File) => void;
  uploading: boolean;
  canUpload: boolean;
}) {
  const t = useTranslations("profile");
  const inputRef = useRef<HTMLInputElement>(null);
  const labelName = name.trim() || "—";

  return (
    <div className="flex flex-col items-center gap-3 sm:items-start">
      <div className="relative">
        {imageUrl ? (
          // eslint-disable-next-line @next/next/no-img-element -- Clerk CDN URLs
          <img
            src={imageUrl}
            alt={t("photoAlt", { name: labelName })}
            width={96}
            height={96}
            className="border-border size-24 rounded-full border object-cover"
          />
        ) : (
          <div
            aria-hidden="true"
            className="bg-forest grid size-24 place-items-center rounded-full text-2xl font-semibold text-white"
          >
            {name.trim() ? getInitials(name) : "—"}
          </div>
        )}
      </div>
      {canUpload && (
        <>
          <input
            ref={inputRef}
            type="file"
            accept="image/*"
            className="sr-only"
            onChange={(e: ChangeEvent<HTMLInputElement>) => {
              const file = e.target.files?.[0];
              if (file) onUpload(file);
              e.target.value = "";
            }}
          />
          <button
            type="button"
            className="border-border hover:bg-hover-bg focus-visible:outline-ring rounded-[6px] border px-3 py-2 text-sm"
            disabled={uploading}
            onClick={() => inputRef.current?.click()}
          >
            {uploading ? t("photoUploading") : t("changePhoto")}
          </button>
        </>
      )}
    </div>
  );
}

function Field({
  label,
  value,
  editing,
  onChange,
  readOnly,
  multiline,
}: {
  label: string;
  value: string;
  editing: boolean;
  onChange?: (value: string) => void;
  readOnly?: boolean;
  multiline?: boolean;
}) {
  if (!editing || readOnly) {
    return (
      <div>
        <dt className="text-muted-ink text-xs">{label}</dt>
        <dd className="mt-1 text-sm whitespace-pre-wrap">{displayOrDash(value)}</dd>
      </div>
    );
  }
  if (multiline) {
    return (
      <label className="block">
        <span className="text-muted-ink text-xs">{label}</span>
        <textarea
          className="border-border focus-visible:outline-ring mt-1 w-full rounded-[6px] border bg-surface px-3 py-2 text-sm"
          rows={2}
          value={value}
          onChange={(e) => onChange?.(e.target.value)}
        />
      </label>
    );
  }
  return (
    <label className="block">
      <span className="text-muted-ink text-xs">{label}</span>
      <input
        className="border-border focus-visible:outline-ring mt-1 w-full rounded-[6px] border bg-surface px-3 py-2 text-sm"
        value={value}
        onChange={(e) => onChange?.(e.target.value)}
      />
    </label>
  );
}

function ProfileBody({
  authName,
  email,
  imageUrl,
  canUpload,
  onUpload,
  uploading,
  photoError,
  showSignOut,
  clerkEnabled,
}: {
  /** From Clerk when signed in; empty shows "—" */
  authName: string;
  email: string;
  imageUrl: string | null;
  canUpload: boolean;
  onUpload: (file: File) => void;
  uploading: boolean;
  photoError: string | null;
  showSignOut: boolean;
  /** When true the edit button is disabled — profile persisted via API (coming soon). */
  clerkEnabled: boolean;
}) {
  const t = useTranslations("profile");
  const profile = useDemoStore((s) => s.profile);
  const updateProfile = useDemoStore((s) => s.updateProfile);

  const [editing, setEditing] = useState(false);
  const [saved, setSaved] = useState(false);
  const [draft, setDraft] = useState<EditableProfile>({
    qualifications: profile.qualifications,
    professionalTitles: profile.professionalTitles,
    notaryRegistration: profile.notaryRegistration,
    jurisdiction: profile.jurisdiction,
    addressLine1: profile.addressLine1,
    addressLine2: profile.addressLine2,
    phone: profile.phone,
  });

  const editable = editing ? draft : profile;
  const headingName = displayOrDash(authName);

  function startEdit() {
    setDraft({
      qualifications: profile.qualifications,
      professionalTitles: profile.professionalTitles,
      notaryRegistration: profile.notaryRegistration,
      jurisdiction: profile.jurisdiction,
      addressLine1: profile.addressLine1,
      addressLine2: profile.addressLine2,
      phone: profile.phone,
    });
    setEditing(true);
    setSaved(false);
  }

  function save() {
    // TODO(api): PATCH /api/v1/me
    updateProfile(draft);
    setEditing(false);
    setSaved(true);
  }

  return (
    <>
      <div className="border-border flex flex-col gap-8 border-b py-5 sm:flex-row sm:items-start">
        <ProfilePhoto
          name={authName}
          imageUrl={imageUrl}
          onUpload={onUpload}
          uploading={uploading}
          canUpload={canUpload}
        />
        <div className="min-w-0 flex-1 space-y-4">
          <div>
            <h2 className="font-heading text-2xl font-semibold tracking-tight">
              {headingName}
            </h2>
            <p className="text-muted-ink mt-1 text-sm">
              {displayOrDash(editable.professionalTitles)}
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
            {!editing ? (
              <button
                type="button"
                className="bg-forest hover:bg-forest/90 focus-visible:outline-ring rounded-[6px] px-3 py-2 text-sm text-white disabled:cursor-not-allowed disabled:opacity-50"
                disabled={clerkEnabled}
                title={clerkEnabled ? t("profileEditComingSoon") : undefined}
                aria-disabled={clerkEnabled}
                onClick={clerkEnabled ? undefined : startEdit}
              >
                {t("edit")}
              </button>
            ) : (
              <>
                <button
                  type="button"
                  className="bg-forest hover:bg-forest/90 focus-visible:outline-ring rounded-[6px] px-3 py-2 text-sm text-white"
                  onClick={save}
                >
                  {t("save")}
                </button>
                <button
                  type="button"
                  className="border-border hover:bg-hover-bg focus-visible:outline-ring rounded-[6px] border px-3 py-2 text-sm"
                  onClick={() => setEditing(false)}
                >
                  {t("cancel")}
                </button>
              </>
            )}
            {showSignOut && (
              <SignOutButton redirectUrl="/sign-in">
                <button
                  type="button"
                  className="border-border hover:bg-hover-bg focus-visible:outline-ring rounded-[6px] border px-3 py-2 text-sm"
                >
                  {t("signOut")}
                </button>
              </SignOutButton>
            )}
          </div>
          {saved && (
            <p aria-live="polite" className="text-forest text-sm">
              {t("saved")}
            </p>
          )}
          {photoError && (
            <p role="alert" className="text-red text-sm">
              {photoError}
            </p>
          )}
        </div>
      </div>

      <section className="border-border border-b py-5">
        <h3 className="text-lg font-semibold">{t("identity")}</h3>
        <dl className="mt-3 grid gap-4 sm:grid-cols-2">
          <Field label={t("nameLabel")} value={authName} editing={false} readOnly />
          <Field label={t("emailLabel")} value={email} editing={false} readOnly />
        </dl>
      </section>

      <section className="border-border border-b py-5">
        <h3 className="text-lg font-semibold">{t("practice")}</h3>
        <dl className="mt-3 grid gap-4 sm:grid-cols-2">
          <Field
            label={t("titlesLabel")}
            value={editable.professionalTitles}
            editing={editing}
            onChange={(v) => setDraft((d) => ({ ...d, professionalTitles: v }))}
          />
          <Field
            label={t("qualificationsLabel")}
            value={editable.qualifications}
            editing={editing}
            multiline
            onChange={(v) => setDraft((d) => ({ ...d, qualifications: v }))}
          />
          <Field
            label={t("notaryCodeLabel")}
            value={editable.notaryRegistration}
            editing={editing}
            onChange={(v) => setDraft((d) => ({ ...d, notaryRegistration: v }))}
          />
          <Field
            label={t("jurisdictionLabel")}
            value={editable.jurisdiction}
            editing={editing}
            onChange={(v) => setDraft((d) => ({ ...d, jurisdiction: v }))}
          />
        </dl>
      </section>

      <section className="py-5">
        <h3 className="text-lg font-semibold">{t("contact")}</h3>
        <dl className="mt-3 grid gap-4 sm:grid-cols-2">
          <Field
            label={t("addressLine1Label")}
            value={editable.addressLine1}
            editing={editing}
            onChange={(v) => setDraft((d) => ({ ...d, addressLine1: v }))}
          />
          <Field
            label={t("addressLine2Label")}
            value={editable.addressLine2}
            editing={editing}
            onChange={(v) => setDraft((d) => ({ ...d, addressLine2: v }))}
          />
          <Field
            label={t("phoneLabel")}
            value={editable.phone}
            editing={editing}
            onChange={(v) => setDraft((d) => ({ ...d, phone: v }))}
          />
        </dl>
      </section>
    </>
  );
}

function clerkDisplayName(user: {
  fullName: string | null;
  firstName: string | null;
  lastName: string | null;
  username: string | null;
}): string {
  const full = user.fullName?.trim();
  if (full) return full;
  const parts = [user.firstName, user.lastName].filter(Boolean).join(" ").trim();
  if (parts) return parts;
  return user.username?.trim() ?? "";
}

function ClerkProfileBody() {
  const t = useTranslations("profile");
  const { user: clerkUser, isLoaded } = useUser();
  const [uploading, setUploading] = useState(false);
  const [photoError, setPhotoError] = useState<string | null>(null);

  const authName = clerkUser ? clerkDisplayName(clerkUser) : "";
  const email =
    clerkUser?.primaryEmailAddress?.emailAddress ??
    (isLoaded ? t("emailUnavailable") : "…");

  async function handlePhotoUpload(file: File) {
    if (!clerkUser) return;
    setUploading(true);
    setPhotoError(null);
    try {
      await clerkUser.setProfileImage({ file });
    } catch {
      setPhotoError(t("photoError"));
    } finally {
      setUploading(false);
    }
  }

  return (
    <ProfileBody
      authName={authName}
      email={email}
      imageUrl={clerkUser?.imageUrl ?? null}
      canUpload={Boolean(clerkUser)}
      onUpload={handlePhotoUpload}
      uploading={uploading}
      photoError={photoError}
      showSignOut={Boolean(clerkUser)}
      clerkEnabled={true}
    />
  );
}

function DemoProfileBody() {
  const t = useTranslations("profile");
  return (
    <ProfileBody
      authName=""
      email={t("emailUnavailable")}
      imageUrl={null}
      canUpload={false}
      onUpload={() => undefined}
      uploading={false}
      photoError={null}
      showSignOut={false}
      clerkEnabled={false}
    />
  );
}

export function ProfileScreen({ clerkEnabled = false }: { clerkEnabled?: boolean }) {
  const t = useTranslations("profile");

  return (
    <AppShell>
      <PageHeader title={t("title")} description={t("description")} />
      <div className="mx-auto max-w-3xl p-6">
        {clerkEnabled ? <ClerkProfileBody /> : <DemoProfileBody />}
        <p className="text-muted-ink border-border border-t pt-4 text-xs">
          <Link href="/settings" className="text-forest underline">
            {t("openSettings")}
          </Link>
        </p>
      </div>
    </AppShell>
  );
}
