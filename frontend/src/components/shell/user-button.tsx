"use client";

import { Show, useUser } from "@clerk/nextjs";
import { CircleUserRound } from "lucide-react";
import { useTranslations } from "next-intl";
import Link from "next/link";

function getInitials(name: string): string {
  return name
    .split(" ")
    .filter(Boolean)
    .slice(0, 2)
    .map((word) => word[0]?.toUpperCase() ?? "")
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

function ProfileLink({
  name,
  label,
  imageUrl,
}: {
  name: string;
  label: string;
  imageUrl?: string | null;
}) {
  return (
    <Link
      href="/profile"
      aria-label={label}
      title={name.trim() || label}
      className="hover:bg-hover-bg focus-visible:outline-ring inline-flex size-10 items-center justify-center rounded-full"
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
        <span className="bg-forest grid size-9 place-items-center rounded-full text-sm font-semibold text-white">
          {name.trim() ? (
            getInitials(name)
          ) : (
            <CircleUserRound aria-hidden="true" className="size-5" strokeWidth={1.5} />
          )}
        </span>
      )}
    </Link>
  );
}

function ClerkHeaderProfile() {
  const t = useTranslations("auth");
  const { user } = useUser();

  return (
    <>
      <Show when="signed-in">
        <ProfileLink
          name={user ? clerkDisplayName(user) : ""}
          label={t("myProfile")}
          imageUrl={user?.imageUrl}
        />
      </Show>
      <Show when="signed-out">
        <Link
          href="/sign-in"
          className="text-forest hover:bg-hover-bg focus-visible:outline-ring inline-flex rounded-[6px] px-2 py-1.5 text-sm font-medium"
        >
          {t("signIn")}
        </Link>
      </Show>
    </>
  );
}

function DemoHeaderProfile() {
  const t = useTranslations("auth");
  return <ProfileLink name="" label={t("myProfile")} />;
}

export function UserButton({ demoMode = false }: { demoMode?: boolean }) {
  return demoMode ? <DemoHeaderProfile /> : <ClerkHeaderProfile />;
}
