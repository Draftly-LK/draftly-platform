"use client";

import {
  CircleHelp,
  Clock3,
  CreditCard,
  FileStack,
  Home,
  Library,
  SearchCheck,
  Menu,
  Settings,
  X,
} from "lucide-react";
import { useTranslations } from "next-intl";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import { isApiEnabled } from "@/lib/api/client";
import { useRecentMatters } from "@/lib/api/use-recent-matters";
import { useDemoStore } from "@/lib/store";
import { BrandMark } from "@/components/ui/brand-mark";
import { IconButton } from "@/components/ui/icon-button";
import { AccountMenu } from "./account-menu";
import { CommandPalette } from "./command-palette";

export function Sidebar() {
  const t = useTranslations("shell");
  const app = useTranslations("app");
  const pathname = usePathname();
  const matters = useDemoStore((state) => state.matters);
  const [open, setOpen] = useState(false);

  useEffect(() => {
    if (!open) return;
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") setOpen(false);
    };
    document.addEventListener("keydown", onKeyDown);
    return () => document.removeEventListener("keydown", onKeyDown);
  }, [open]);
  const groups = [
    {
      key: "work",
      label: t("groupWork"),
      links: [
        { href: "/", label: t("home"), icon: Home },
        { href: "/matters", label: t("matters"), icon: FileStack },
        { href: "/history", label: t("history"), icon: Clock3 },
      ],
    },
    {
      key: "knowledge",
      label: t("groupKnowledge"),
      links: [
        { href: "/library", label: t("library"), icon: Library },
        { href: "/research", label: t("research"), icon: SearchCheck },
      ],
    },
  ];
  const footerLinks = [
    { href: "/billing", label: t("billing"), icon: CreditCard },
    { href: "/settings", label: t("settings"), icon: Settings },
    { href: "/help", label: t("help"), icon: CircleHelp },
  ];
  const isActive = (href: string) => pathname === href || (href !== "/" && pathname.startsWith(href));
  return (
    <>
      <div className="fixed left-3 top-3 z-20 md:hidden">
        <IconButton
          label={t("openNavigation")}
          className="border-border-strong bg-surface"
          onClick={() => setOpen(true)}
        >
          <Menu className="size-5" strokeWidth={1.5} />
        </IconButton>
      </div>
      {open && (
        <button
          aria-label={t("close")}
          className="bg-ink/25 fixed inset-0 z-20 md:hidden"
          onClick={() => setOpen(false)}
        />
      )}
      <aside
        data-app-chrome
        data-surface="inverse"
        className={`bg-navy-950 text-on-dark fixed inset-y-0 left-0 z-20 flex w-[var(--sidebar-width)] flex-col border-r border-white/5 p-3 transition-transform md:translate-x-0 ${open ? "translate-x-0" : "-translate-x-full"}`}
      >
        <div className="flex h-12 items-center gap-3 px-2 py-2 box-content">
          <BrandMark tone="white" className="size-8 shrink-0" />
          <div className="min-w-0 flex-1">
            <div className="font-display text-xl font-semibold leading-none text-white">
              {app("name")}
            </div>
            <div className="text-on-dark-muted mt-1 truncate text-xs font-medium">
              {t("workspace")}
            </div>
          </div>
          <IconButton
            label={t("close")}
            className="text-on-dark hover:bg-white/10 md:hidden"
            onClick={() => setOpen(false)}
          >
            <X className="size-5" />
          </IconButton>
        </div>
        {/* Creating a matter starts from the Home banner and the Matters
            page; a second gold button here read as a duplicate. */}
        <div className="mt-3">
          <CommandPalette tone="dark" />
        </div>
        <div className="mt-5 min-h-0 flex-1 overflow-y-auto pr-1">
          <nav aria-label={t("workspace")} className="space-y-5">
            {groups.map((group) => (
              <div key={group.key}>
                <div className="text-on-dark-muted mb-1 px-3 text-xs font-medium">{group.label}</div>
                <div className="space-y-0.5">
                  {group.links.map((link) => (
                    <NavLink key={link.href} {...link} active={isActive(link.href)} onNavigate={() => setOpen(false)} />
                  ))}
                </div>
              </div>
            ))}
          </nav>
          {isApiEnabled() ? <ApiRecentMatters /> : <RecentMatters matters={matters} />}
        </div>
        <div className="shrink-0 border-t border-white/10 pt-3">
          <nav aria-label={t("account")} className="space-y-0.5">
            {footerLinks.map((link) => (
              <NavLink key={link.href} {...link} active={isActive(link.href)} onNavigate={() => setOpen(false)} />
            ))}
          </nav>
          <div className="mt-2 border-t border-white/10 pt-2">
            <AccountMenu />
          </div>
        </div>
      </aside>
    </>
  );
}

function NavLink({
  href,
  label,
  icon: Icon,
  active,
  onNavigate,
}: {
  href: string;
  label: string;
  icon: typeof Home;
  active: boolean;
  onNavigate: () => void;
}) {
  return (
    <Link
      href={href}
      onClick={onNavigate}
      aria-current={active ? "page" : undefined}
      // Square on the left, where the 3px gold marker runs the full height;
      // rounded on the right only. The active fill is a light veil, not a block.
      className={`relative flex min-h-10 items-center gap-3 rounded-r rounded-l-none px-3 text-sm ${active ? "bg-white/[0.07] font-medium text-white before:absolute before:inset-y-0 before:left-0 before:w-[3px] before:bg-gold" : "text-on-dark-muted hover:bg-white/5 hover:text-white"}`}
    >
      <Icon aria-hidden="true" className="size-5 shrink-0" strokeWidth={1.5} />
      {label}
    </Link>
  );
}

/** Up to five recent matters; nothing at all when there are none (Home already says so). */
function ApiRecentMatters() {
  const { matters, failed } = useRecentMatters();
  const t = useTranslations("shell");
  if (failed) {
    return <p className="mt-6 px-3 text-xs text-red-bg">{t("recentLoadFailed")}</p>;
  }
  return <RecentMatters matters={matters} />;
}

function RecentMatters({
  matters,
}: {
  matters: readonly { id: string; reference: string; clientReference?: string | null }[];
}) {
  const t = useTranslations("shell");
  if (matters.length === 0) return null;
  return (
    <div className="mt-6 border-t border-white/10 pt-4">
      <div className="text-on-dark-muted mb-1 px-3 text-xs font-medium">{t("recentMatters")}</div>
      {matters.slice(0, 5).map((matter) => (
        <Link
          key={matter.id}
          href={`/matters/${matter.id}`}
          className="text-on-dark-muted flex min-h-9 items-baseline gap-2 rounded px-3 py-1.5 text-sm hover:bg-white/5 hover:text-white"
        >
          <span className="shrink-0 tabular-nums">{matter.reference}</span>
          {matter.clientReference && matter.clientReference.trim() !== matter.reference.trim() ? (
            <span className="truncate text-xs opacity-70">{matter.clientReference}</span>
          ) : null}
        </Link>
      ))}
    </div>
  );
}
