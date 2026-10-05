"use client";

import { Show, useClerk, useUser } from "@clerk/nextjs";
import { ChevronsUpDown, CircleHelp, CircleUserRound, CreditCard, LogOut, Settings, UserRound } from "lucide-react";
import { useTranslations } from "next-intl";
import Link from "next/link";
import { Menu, type MenuDivider, type MenuItem } from "@/components/ui/menu";
import { Tooltip } from "@/components/ui/tooltip";
import { isRailActive } from "./sidebar-state";
import { clerkDisplayName, getInitials, useDemoMode } from "./user-button";

function Avatar({ name, imageUrl }: { name: string; imageUrl?: string | null }) {
  return imageUrl ? (
    // eslint-disable-next-line @next/next/no-img-element -- Clerk CDN
    <img src={imageUrl} alt="" width={32} height={32} className="size-8 shrink-0 rounded-full object-cover" />
  ) : (
    <span className="grid size-8 shrink-0 place-items-center rounded-full bg-white/15 text-xs font-semibold text-white">
      {name.trim() ? (
        getInitials(name)
      ) : (
        <CircleUserRound aria-hidden="true" className="size-5" strokeWidth={1.5} />
      )}
    </span>
  );
}

export function AccountMenuView({
  name,
  imageUrl,
  onSignOut,
}: {
  name: string;
  imageUrl?: string | null;
  /** Absent in demo mode, where there is no session to end. */
  onSignOut?: () => void;
}) {
  const t = useTranslations("shell");
  const auth = useTranslations("auth");
  const profile = useTranslations("profile");
  const items: (MenuItem | MenuDivider)[] = [
    { key: "profile", label: auth("myProfile"), icon: UserRound, href: "/profile" },
    { key: "settings", label: t("settings"), icon: Settings, href: "/settings" },
    { key: "billing", label: t("billing"), icon: CreditCard, href: "/billing" },
    { key: "help", label: t("help"), icon: CircleHelp, href: "/help" },
    // Sign out only exists with a real session; offline there is nothing to end.
    ...(onSignOut
      ? [
          { key: "divider", divider: true as const },
          { key: "sign-out", label: profile("signOut"), icon: LogOut, onSelect: onSignOut },
        ]
      : []),
  ];
  return (
    // In the rail only the avatar shows, so the tooltip names the person.
    <Tooltip label={name.trim() || t("account")} enabled={isRailActive}>
      <Menu
        label={t("accountMenu")}
        side="top"
        rootClassName="w-full"
        // The rail clips anything wider than itself, so its popover is drawn in a portal.
        portalWhen={isRailActive}
        triggerClassName="flex min-h-12 w-full cursor-pointer items-center gap-3 rounded px-2 py-2 text-left text-on-dark hover:bg-white/10 rail:justify-center rail:gap-0 rail:px-0"
        trigger={
          <>
            <Avatar name={name} imageUrl={imageUrl} />
            <span className="min-w-0 flex-1 truncate text-sm font-medium rail:hidden">{name.trim() || t("account")}</span>
            <ChevronsUpDown aria-hidden="true" className="size-4 shrink-0 text-on-dark-muted rail:hidden" strokeWidth={1.5} />
          </>
        }
        items={items}
      />
    </Tooltip>
  );
}

function ClerkAccountMenu() {
  const { user } = useUser();
  const { signOut } = useClerk();
  const auth = useTranslations("auth");
  return (
    <>
      <Show when="signed-in">
        <AccountMenuView
          name={user ? clerkDisplayName(user) : ""}
          imageUrl={user?.imageUrl}
          onSignOut={() => void signOut({ redirectUrl: "/sign-in" })}
        />
      </Show>
      <Show when="signed-out">
        <Link
          href="/sign-in"
          className="text-on-dark flex min-h-10 items-center rounded px-3 text-sm font-medium hover:bg-white/10"
        >
          {auth("signIn")}
        </Link>
      </Show>
    </>
  );
}

/** Avatar, name and a chevron at the foot of the sidebar; opens Profile, Settings, Billing and Sign out. */
export function AccountMenu() {
  return useDemoMode() ? <AccountMenuView name="" /> : <ClerkAccountMenu />;
}
