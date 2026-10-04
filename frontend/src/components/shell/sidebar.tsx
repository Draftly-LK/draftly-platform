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
  const links = [
    { href: "/", label: t("home"), icon: Home },
    { href: "/matters", label: t("matters"), icon: FileStack },
    { href: "/library", label: t("library"), icon: Library },
    { href: "/research", label: t("research"), icon: SearchCheck },
    { href: "/history", label: t("history"), icon: Clock3 },
    { href: "/billing", label: t("billing"), icon: CreditCard },
  ];
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
        className={`bg-navy-950 text-on-dark fixed inset-y-0 left-0 z-20 flex w-[244px] flex-col border-r border-white/5 p-3 transition-transform md:translate-x-0 ${open ? "translate-x-0" : "-translate-x-full"}`}
      >
        <div className="flex h-12 items-center gap-3 px-2 py-2 box-content">
          <BrandMark tone="white" className="size-8 shrink-0" />
          <div className="min-w-0 flex-1">
            <div className="font-display text-[22px] font-semibold leading-none text-white">
              {app("name")}
            </div>
            <div className="text-on-dark-muted mt-1 truncate text-[11px] font-medium uppercase tracking-[0.08em]">
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
          <nav className="space-y-0.5" aria-label={t("workspace")}>
            {links.map(({ href, label, icon: Icon }) => {
              const active = pathname === href || (href !== "/" && pathname.startsWith(href));
              return (
                <Link
                  key={href}
                  href={href}
                  onClick={() => setOpen(false)}
                  aria-current={active ? "page" : undefined}
                  // Square on the left, where the gold marker runs the full
                  // height; rounded on the right only.
                  className={`relative flex min-h-10 items-center gap-3 rounded-r rounded-l-none px-3 ${active ? "bg-white/10 font-medium text-white before:absolute before:inset-y-0 before:left-0 before:w-[3px] before:bg-gold" : "text-on-dark-muted hover:bg-white/5 hover:text-white"}`}
                >
                  <Icon className="size-5" strokeWidth={1.5} />
                  {label}
                </Link>
              );
            })}
          </nav>
          <div className="mt-6 border-t border-white/10 pt-4">
            <div className="text-on-dark-muted px-3 text-[11px] font-semibold uppercase tracking-[0.08em]">
              {t("recentMatters")}
            </div>
            {isApiEnabled() ? (
              <ApiRecentMatterLinks />
            ) : (
              <RecentMatterLinks matters={matters.slice(0, 2)} />
            )}
          </div>
        </div>
        <div className="shrink-0 border-t border-white/10 pt-3">
          <div className="space-y-0.5">
            <Link
              className="text-on-dark-muted flex min-h-10 items-center gap-3 rounded px-3 hover:bg-white/5 hover:text-white"
              href="/settings"
            >
              <Settings className="size-5" strokeWidth={1.5} />
              {t("settings")}
            </Link>
            <Link
              className="text-on-dark-muted flex min-h-10 items-center gap-3 rounded px-3 hover:bg-white/5 hover:text-white"
              href="/help"
            >
              <CircleHelp className="size-5" strokeWidth={1.5} />
              {t("help")}
            </Link>
          </div>
        </div>
      </aside>
    </>
  );
}

function ApiRecentMatterLinks() {
  const { matters, loading, failed } = useRecentMatters();
  const t = useTranslations("shell");
  if (loading) {
    return (
      <p className="text-on-dark-muted px-3 py-2 text-xs">{t("recentLoading")}</p>
    );
  }
  if (failed) {
    return (
      <p className="px-3 py-2 text-red-bg text-xs">{t("recentLoadFailed")}</p>
    );
  }
  if (matters.length === 0) {
    return (
      <p className="text-on-dark-muted px-3 py-2 text-xs">{t("recentEmpty")}</p>
    );
  }
  return <RecentMatterLinks matters={matters.slice(0, 2)} />;
}

function RecentMatterLinks({
  matters,
}: {
  matters: readonly { id: string; reference: string }[];
}) {
  return matters.map((matter) => (
    <Link
      key={matter.id}
      href={`/matters/${matter.id}`}
      className="text-on-dark-muted mt-1 flex items-center gap-2 truncate rounded px-3 py-2 text-sm tabular-nums hover:bg-white/5 hover:text-white"
    >
      <span className="bg-gold size-1.5 shrink-0 rounded-full opacity-80" aria-hidden="true" />
      <span className="truncate">{matter.reference}</span>
    </Link>
  ));
}
