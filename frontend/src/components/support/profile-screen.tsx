"use client";

import {
  useCallback,
  useEffect,
  useRef,
  useState,
  type ChangeEvent,
} from "react";
import Link from "next/link";
import { SignOutButton, useUser } from "@clerk/nextjs";
import { useTranslations } from "next-intl";
import { AppShell } from "@/components/shell/app-shell";
import { PageHeader } from "@/components/shell/page-header";
import { Button } from "@/components/ui/button";
import { getMe, updateMe } from "@/lib/api/auth";
import { ApiError } from "@/lib/api/client";
import { useTokenProvider } from "@/lib/api/use-token-provider";
import {
  diffProfile,
  pickEditableProfile,
  toEditableProfile,
  type EditableProfile,
  type ProfileFieldPatch,
} from "@/lib/profile/profile-fields";
import { useDemoStore } from "@/lib/store";

function getInitials(name: string): string {
  return name
    .split(" ")
    .filter(Boolean)
    .slice(0, 2)
    .map((w) => w[0]?.toUpperCase() ?? "")
    .join("");
}

function displayOrDash(value: string): string {
  const trimmed = value.trim();
  return trimmed.length > 0 ? trimmed : "—";
}

/** Clerk's account-holder display name, independent of Draftly's own `displayName`. */
function clerkDisplayName(user: {
  fullName: string | null;
  firstName: string | null;
  lastName: string | null;
  username: string | null;
}): string {
  const full = user.fullName?.trim();
  if (full) return full;
  const parts = [user.firstName, user.lastName]
    .filter(Boolean)
    .join(" ")
    .trim();
  if (parts) return parts;
  return user.username?.trim() ?? "";
}

/** Everything about the signed-in identity: who they are, and photo upload. */
interface IdentityProps {
  /** Clerk's account name — read-only, shown only when `showSignOut` is true. */
  signInName: string;
  email: string;
  imageUrl: string | null;
  canUpload: boolean;
  onUpload?: (file: File) => void;
  uploading: boolean;
  photoError: string | null;
  photoSuccess: boolean;
  showSignOut: boolean;
}

const MAX_PHOTO_BYTES = 10 * 1024 * 1024; // Clerk's profile-image upload limit

/** Clerk profile-photo upload, with client-side validation and result feedback. */
function usePhotoUpload(clerkUser: ReturnType<typeof useUser>["user"]) {
  const t = useTranslations("profile");
  const [uploading, setUploading] = useState(false);
  const [photoError, setPhotoError] = useState<string | null>(null);
  const [photoSuccess, setPhotoSuccess] = useState(false);

  const handlePhotoUpload = useCallback(
    async (file: File) => {
      if (!clerkUser) return;
      setPhotoSuccess(false);
      if (!file.type.startsWith("image/")) {
        setPhotoError(t("photoInvalidType"));
        return;
      }
      if (file.size > MAX_PHOTO_BYTES) {
        setPhotoError(t("photoTooLarge"));
        return;
      }
      setUploading(true);
      setPhotoError(null);
      try {
        await clerkUser.setProfileImage({ file });
        setPhotoSuccess(true);
      } catch (error: unknown) {
        console.error("Draftly profile photo upload failed:", error);
        setPhotoError(t("photoError"));
      } finally {
        setUploading(false);
      }
    },
    [clerkUser, t],
  );

  return { uploading, photoError, photoSuccess, handlePhotoUpload };
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
  onUpload?: (file: File) => void;
  uploading: boolean;
  canUpload: boolean;
}) {
  const t = useTranslations("profile");
  const inputRef = useRef<HTMLInputElement>(null);
  const labelName = name.trim() || "—";

  return (
    <div className="flex flex-col items-center gap-3 sm:items-start">
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
      {canUpload && (
        <>
          <input
            ref={inputRef}
            type="file"
            accept="image/*"
            className="sr-only"
            onChange={(e: ChangeEvent<HTMLInputElement>) => {
              const file = e.target.files?.[0];
              if (file) onUpload?.(file);
              e.target.value = "";
            }}
          />
          <button
            type="button"
            className="border-border hover:bg-hover-bg focus-visible:outline-ring rounded-control border px-3 py-2 text-sm"
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
  multiline,
}: {
  label: string;
  value: string;
  /** Read-only fields simply never pass `editing={true}`. */
  editing: boolean;
  onChange?: (value: string) => void;
  multiline?: boolean;
}) {
  if (!editing) {
    return (
      <div>
        <dt className="text-muted-ink text-xs">{label}</dt>
        <dd className="mt-1 whitespace-pre-wrap text-sm">
          {displayOrDash(value)}
        </dd>
      </div>
    );
  }
  if (multiline) {
    return (
      <label className="block">
        <span className="text-muted-ink text-xs">{label}</span>
        <textarea
          className="border-border focus-visible:outline-ring bg-surface mt-1 w-full rounded border px-3 py-2 text-sm"
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
        className="border-border focus-visible:outline-ring rounded-control bg-surface mt-1 w-full border px-3 py-2 text-sm"
        value={value}
        onChange={(e) => onChange?.(e.target.value)}
      />
    </label>
  );
}

function ProfileBody({
  identity,
  profile,
  onSave,
  savedMessage,
}: {
  identity: IdentityProps;
  /** Current saved values — the source of truth outside edit mode. */
  profile: EditableProfile;
  /** Persists a changed-fields diff. Demo path resolves immediately; the
   * API-backed path awaits `PATCH /me` and may reject. */
  onSave: (changes: ProfileFieldPatch) => Promise<void>;
  savedMessage: string;
}) {
  const t = useTranslations("profile");

  const [editing, setEditing] = useState(false);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [draft, setDraft] = useState<EditableProfile>(profile);

  const editable = editing ? draft : profile;
  const headingName = displayOrDash(editable.displayName);

  function startEdit() {
    setDraft(profile);
    setEditing(true);
    setSaved(false);
    setSaveError(null);
  }

  function cancelEdit() {
    setDraft(profile);
    setEditing(false);
    setSaveError(null);
  }

  async function save() {
    const changes = diffProfile(profile, draft);
    // Nothing actually changed — exit edit mode without a request or a
    // (misleading) "saved" confirmation.
    if (Object.keys(changes).length === 0) {
      setEditing(false);
      setSaveError(null);
      return;
    }
    setSaving(true);
    setSaved(false);
    setSaveError(null);
    try {
      await onSave(changes);
      setEditing(false);
      setSaved(true);
    } catch (error: unknown) {
      if (error instanceof ApiError) {
        console.error(
          `Draftly profile save failed (${error.code}, correlation ${error.correlationId}): ${error.message}`,
        );
      } else {
        console.error("Draftly profile save failed:", error);
      }
      setSaveError(t("saveFailed"));
    } finally {
      setSaving(false);
    }
  }

  return (
    <>
      <div className="border-border flex flex-col gap-6 border-b pb-5 sm:flex-row sm:items-start">
        <ProfilePhoto
          name={editable.displayName}
          imageUrl={identity.imageUrl}
          onUpload={identity.onUpload}
          uploading={identity.uploading}
          canUpload={identity.canUpload}
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
              <Button type="button" onClick={startEdit}>
                {t("edit")}
              </Button>
            ) : (
              <>
                {/* The one gold button while editing. */}
                <Button
                  type="button"
                  variant="primary"
                  loading={saving}
                  onClick={() => void save()}
                >
                  {saving ? t("saving") : t("save")}
                </Button>
                <Button type="button" disabled={saving} onClick={cancelEdit}>
                  {t("cancel")}
                </Button>
              </>
            )}
            {identity.showSignOut && (
              <SignOutButton redirectUrl="/sign-in">
                <Button type="button">{t("signOut")}</Button>
              </SignOutButton>
            )}
          </div>
          {saved && (
            <p aria-live="polite" className="text-forest text-sm">
              {savedMessage}
            </p>
          )}
          {saveError && (
            <p role="alert" className="text-red text-sm">
              {saveError}
            </p>
          )}
          {identity.photoError && (
            <p role="alert" className="text-red text-sm">
              {identity.photoError}
            </p>
          )}
          {identity.photoSuccess && !identity.photoError && (
            <p aria-live="polite" className="text-forest text-sm">
              {t("photoUploaded")}
            </p>
          )}
        </div>
      </div>

      <section className="border-border border-b py-5">
        <h3 className="text-lg font-semibold">{t("identity")}</h3>
        <dl className="mt-3 grid gap-4 sm:grid-cols-2">
          <Field
            label={t("nameLabel")}
            value={editable.displayName}
            editing={editing}
            onChange={(v) => setDraft((d) => ({ ...d, displayName: v }))}
          />
          {identity.showSignOut && (
            <Field
              label={t("signInAccountLabel")}
              value={identity.signInName}
              editing={false}
            />
          )}
          <Field
            label={t("emailLabel")}
            value={identity.email}
            editing={false}
          />
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

type LoadStatus = "loading" | "ready" | "error";

/** Persistence via `GET/PATCH /me`. Requires a Clerk-issued token, so this is
 * only mounted when Clerk is configured. */
function ApiPersistedProfile({
  identity,
  getToken,
}: {
  identity: IdentityProps;
  getToken: ReturnType<typeof useTokenProvider>;
}) {
  const t = useTranslations("profile");
  const tApp = useTranslations("app");
  const [status, setStatus] = useState<LoadStatus>("loading");
  const [profile, setProfile] = useState<EditableProfile | null>(null);
  // Tracks the in-flight request so a rapid Retry (or unmount) aborts the
  // superseded one instead of racing it — last response in wins, and no
  // setState fires after unmount.
  const controllerRef = useRef<AbortController | null>(null);

  const loadProfile = useCallback(() => {
    controllerRef.current?.abort();
    const controller = new AbortController();
    controllerRef.current = controller;
    setStatus("loading");
    getMe(getToken, controller.signal)
      .then((user) => {
        if (controller.signal.aborted) return;
        setProfile(toEditableProfile(user));
        setStatus("ready");
      })
      .catch((error: unknown) => {
        if (controller.signal.aborted) return;
        if (error instanceof ApiError) {
          console.error(
            `Draftly profile load failed (${error.code}, correlation ${error.correlationId}): ${error.message}`,
          );
        } else {
          console.error("Draftly profile load failed:", error);
        }
        setStatus("error");
      });
  }, [getToken]);

  useEffect(() => {
    loadProfile();
    return () => controllerRef.current?.abort();
  }, [loadProfile]);

  async function handleSave(changes: ProfileFieldPatch) {
    const updated = await updateMe(getToken, changes);
    setProfile(toEditableProfile(updated));
  }

  if (status === "loading") {
    return <p className="text-muted-ink py-8 text-sm">{tApp("loading")}</p>;
  }

  if (status === "error" || !profile) {
    return (
      <div className="py-8">
        <p role="alert" className="text-red text-sm">
          {t("loadFailed")}
        </p>
        <button
          type="button"
          className="border-border hover:bg-hover-bg focus-visible:outline-ring rounded-control mt-3 border px-3 py-2 text-sm"
          onClick={loadProfile}
        >
          {tApp("retry")}
        </button>
      </div>
    );
  }

  return (
    <ProfileBody
      identity={identity}
      profile={profile}
      onSave={handleSave}
      savedMessage={t("savedRemote")}
    />
  );
}

/** Persistence via the local demo store — used both when the backend isn't
 * configured (`DemoProfileBody`) and when Clerk is on but the API isn't
 * (identity still works; profile fields fall back to local storage). */
function LocalPersistedProfile({ identity }: { identity: IdentityProps }) {
  const t = useTranslations("profile");
  const storeProfile = useDemoStore((s) => s.profile);
  const updateProfile = useDemoStore((s) => s.updateProfile);

  return (
    <ProfileBody
      identity={identity}
      profile={pickEditableProfile(storeProfile)}
      onSave={(changes) => {
        updateProfile(changes);
        return Promise.resolve();
      }}
      savedMessage={t("saved")}
    />
  );
}

function ClerkProfileBody({ apiEnabled }: { apiEnabled: boolean }) {
  const t = useTranslations("profile");
  const { user: clerkUser, isLoaded } = useUser();
  const getToken = useTokenProvider();
  const photo = usePhotoUpload(clerkUser);

  const email =
    clerkUser?.primaryEmailAddress?.emailAddress ??
    (isLoaded ? t("emailUnavailable") : "…");

  const identity: IdentityProps = {
    signInName: clerkUser ? clerkDisplayName(clerkUser) : "",
    email,
    imageUrl: clerkUser?.imageUrl ?? null,
    canUpload: Boolean(clerkUser),
    onUpload: photo.handlePhotoUpload,
    uploading: photo.uploading,
    photoError: photo.photoError,
    photoSuccess: photo.photoSuccess,
    showSignOut: Boolean(clerkUser),
  };

  // `apiEnabled` is an inlined build-time boolean (see `isApiEnabled()`), so
  // it never flips between renders and this branch doesn't shuffle hook
  // order — same pattern as `ProvisionGate`.
  return apiEnabled ? (
    <ApiPersistedProfile identity={identity} getToken={getToken} />
  ) : (
    <LocalPersistedProfile identity={identity} />
  );
}

function DemoProfileBody() {
  const t = useTranslations("profile");
  const identity: IdentityProps = {
    signInName: "",
    email: t("emailUnavailable"),
    imageUrl: null,
    canUpload: false,
    uploading: false,
    photoError: null,
    photoSuccess: false,
    showSignOut: false,
  };
  return <LocalPersistedProfile identity={identity} />;
}

export function ProfileScreen({
  clerkEnabled = false,
  apiEnabled = false,
}: {
  clerkEnabled?: boolean;
  apiEnabled?: boolean;
}) {
  const t = useTranslations("profile");

  return (
    <AppShell>
      <PageHeader title={t("title")} description={t("description")} />
      <div className="mx-auto w-full max-w-[1240px] p-6">
        {clerkEnabled ? (
          <ClerkProfileBody apiEnabled={apiEnabled} />
        ) : (
          <DemoProfileBody />
        )}
        <p className="text-muted-ink border-border border-t pt-4 text-xs">
          <Link href="/settings" className="text-forest underline">
            {t("openSettings")}
          </Link>
        </p>
      </div>
    </AppShell>
  );
}
