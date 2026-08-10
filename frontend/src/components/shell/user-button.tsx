"use client";

/**
 * Sidebar profile control — navigates to /profile.
 * Clerk: real name + photo from session. Demo: "My profile" label only.
 */

import Link from "next/link";
import { Show, useUser } from "@clerk/nextjs";
import { useTranslations } from "next-intl";

function getInitials(name: string): string {
  return name
    .split(" ")
    .filter(Boolean)
    .slice(0, 2)
    .map((w) => w[0]?.toUpperCase() ?? "")
    .join("");
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

function ProfileLinkRow({
  name,
  subtitle,
  imageUrl,
}: {
  name: string;
  subtitle: string;
  imageUrl?: string | null;
}) {
  const initials = name.trim() ? getInitials(name) : "?";

  return (
    <Link
      href="/profile"
      className="hover:bg-hover-bg focus-visible:outline-ring flex items-center gap-3 rounded-[6px] px-3 py-2"
    >
      {imageUrl ? (
        // eslint-disable-next-line @next/next/no-img-element -- Clerk CDN
        <img
          src={imageUrl}
          alt=""
          width={36}
          height={36}
          className="ring-forest/30 size-9 rounded-full object-cover ring-2"
        />
      ) : (
        <div
          aria-hidden="true"
          className="bg-forest grid size-9 shrink-0 place-items-center rounded-full text-sm font-semibold text-white"
        >
          {initials}
        </div>
      )}
      <div className="min-w-0 flex-1">
        <div className="truncate text-sm font-medium leading-tight">
          {name.trim() || subtitle}
        </div>
        {name.trim() ? (
          <span className="text-muted-ink text-xs">{subtitle}</span>
        ) : null}
      </div>
    </Link>
  );
}

function ClerkSidebarProfile() {
  const t = useTranslations("auth");
  const { user } = useUser();

  return (
    <>
      <Show when="signed-in">
        <ProfileLinkRow
          name={user ? clerkDisplayName(user) : ""}
          subtitle={t("myProfile")}
          imageUrl={user?.imageUrl}
        />
      </Show>
      <Show when="signed-out">
        <div className="px-3 py-2">
          <Link
            href="/sign-in"
            className="text-forest hover:bg-hover-bg focus-visible:outline-ring inline-flex rounded-[6px] px-2 py-1.5 text-sm font-medium"
          >
            {t("signIn")}
          </Link>
        </div>
      </Show>
    </>
  );
}

function DemoSidebarProfile() {
  const t = useTranslations("auth");
  return <ProfileLinkRow name="" subtitle={t("myProfile")} />;
}

export function UserButton({ demoMode = false }: { demoMode?: boolean }) {
  // demoMode is computed server-side via isClerkConfigured() in AppShell.
  if (demoMode) {
    return <DemoSidebarProfile />;
  }
  return <ClerkSidebarProfile />;
}
