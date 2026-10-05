"use client";

import {
  Clock3,
  FileStack,
  Home,
  Library,
  SearchCheck,
  Menu,
  PanelLeftClose,
  PanelLeftOpen,
  X,
} from "lucide-react";
import { useTranslations } from "next-intl";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { isApiEnabled } from "@/lib/api/client";
import { useRecentMatters } from "@/lib/api/use-recent-matters";
import { useMediaQuery } from "@/lib/use-media-query";
import { useDemoStore } from "@/lib/store";
import { BrandMark } from "@/components/ui/brand-mark";
import { IconButton } from "@/components/ui/icon-button";
import { Tooltip } from "@/components/ui/tooltip";
import { AccountMenu } from "./account-menu";
import { CommandPalette } from "./command-palette";
import { NavyBackdrop } from "./navy-backdrop";
import { isRailActive, useSidebarState } from "./sidebar-state";

export function Sidebar() {
  const t = useTranslations("shell");
  const app = useTranslations("app");
  const pathname = usePathname();
  const matters = useDemoStore((state) => state.matters);
  const [open, setOpen] = useState(false);
  const { collapsed, toggle } = useSidebarState();
  // From 1024px the sidebar is a fixed rail; below that it is a drawer.
  const desktop = useMediaQuery("(min-width: 1024px)");
  const drawer = desktop === false;
  const asideRef = useRef<HTMLElement>(null);
  const openerRef = useRef<HTMLDivElement>(null);
  const wasOpen = useRef(false);

  // Drawer behaviour: Escape closes, Tab stays inside, focus moves in on open
  // and returns to the menu button on close.
  useEffect(() => {
    if (!open) {
      if (wasOpen.current) openerRef.current?.querySelector("button")?.focus();
      wasOpen.current = false;
      return;
    }
    wasOpen.current = true;
    asideRef.current?.querySelector<HTMLElement>("[data-drawer-close]")?.focus();
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        setOpen(false);
        return;
      }
      if (event.key !== "Tab" || !asideRef.current) return;
      const focusable = Array.from(
        asideRef.current.querySelectorAll<HTMLElement>("a[href], button:not([disabled]), [tabindex]:not([tabindex='-1'])"),
      );
      const first = focusable[0];
      const last = focusable.at(-1);
      if (!first || !last) return;
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    };
    document.addEventListener("keydown", onKeyDown);
    return () => document.removeEventListener("keydown", onKeyDown);
  }, [open]);

  // Leaving drawer width with the drawer open must not strand it open.
  useEffect(() => {
    if (desktop) setOpen(false);
  }, [desktop]);
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
  const isActive = (href: string) => pathname === href || (href !== "/" && pathname.startsWith(href));
  return (
    <>
      <div ref={openerRef} className="fixed left-3 top-3 z-20 lg:hidden">
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
          className="bg-scrim fixed inset-0 z-20 lg:hidden"
          onClick={() => setOpen(false)}
        />
      )}
      <aside
        ref={asideRef}
        data-app-chrome
        data-surface="inverse"
        // Closed, the drawer is off-screen and must not be reachable by keyboard.
        inert={drawer && !open ? true : undefined}
        id="app-sidebar"
        {...(drawer && open ? { role: "dialog", "aria-modal": true, "aria-label": t("workspace") } : {})}
        // A 1px edge and a soft shadow lift the sidebar slightly above the header; the shadow falls on the header and the page.
        className={`bg-surface-inverse text-on-dark fixed inset-y-0 left-0 z-20 w-[var(--sidebar-width)] overflow-hidden border-r border-white/[0.08] p-3 shadow-sidebar transition-[transform,width] duration-[180ms] ease-out lg:translate-x-0 ${open ? "translate-x-0" : "-translate-x-full"}`}
      >
        <NavyBackdrop anchor="origin" />
        <div className="relative z-10 flex h-full flex-col">
        <div className="box-content flex h-12 items-center gap-3 px-2 py-2 rail:h-auto rail:flex-col rail:gap-2 rail:px-0">
          <BrandMark tone="white" className="size-8 shrink-0" />
          {/* The rail keeps the logo mark only. */}
          <div className="min-w-0 flex-1 rail:hidden">
            <div className="font-display text-xl font-semibold leading-none text-white">
              {app("name")}
            </div>
            <div className="text-on-dark-muted mt-1 truncate text-xs font-medium">
              {t("workspace")}
            </div>
          </div>
          {/* Desktop only: below 1024px the sidebar is a drawer and has no collapsed state. */}
          <Tooltip label={collapsed ? t("expandSidebar") : t("collapseSidebar")} shortcut={t("sidebarShortcut")}>
            <IconButton
              label={collapsed ? t("expandSidebar") : t("collapseSidebar")}
              aria-expanded={!collapsed}
              aria-controls="app-sidebar"
              aria-keyshortcuts={"Control+\\"}
              className="hidden text-on-dark-muted hover:bg-white/10 hover:text-white lg:inline-flex"
              onClick={toggle}
            >
              {collapsed ? (
                <PanelLeftOpen aria-hidden="true" className="size-5" strokeWidth={1.5} />
              ) : (
                <PanelLeftClose aria-hidden="true" className="size-5" strokeWidth={1.5} />
              )}
            </IconButton>
          </Tooltip>
          <IconButton
            label={t("close")}
            data-drawer-close
            className="text-on-dark hover:bg-white/10 lg:hidden"
            onClick={() => setOpen(false)}
          >
            <X className="size-5" />
          </IconButton>
        </div>
        {/* Creating a matter starts from the Home banner and the Matters
            page; a second gold button here read as a duplicate. */}
        <div className="mt-3">
          <Tooltip label={t("search")} shortcut={t("searchShortcut")} enabled={isRailActive}>
            <CommandPalette tone="dark" />
          </Tooltip>
        </div>
        <div className="mt-5 min-h-0 flex-1 overflow-y-auto pr-1">
          <nav aria-label={t("workspace")} className="space-y-5 rail:space-y-3">
            {groups.map((group, index) => (
              <div key={group.key} className={index > 0 ? "rail:border-t rail:border-white/10 rail:pt-3" : undefined}>
                <div className="text-on-dark-muted mb-1 px-3 text-xs font-medium rail:hidden">{group.label}</div>
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
    <Tooltip label={label} enabled={isRailActive}>
      <Link
        href={href}
        onClick={onNavigate}
        aria-current={active ? "page" : undefined}
        // Square on the left, where the 3px gold marker runs the full height;
        // rounded on the right only. Hover is a light veil (white 5%); the active
        // item is clearly stronger (white 10% plus the gold marker). In the rail the
        // label is visually hidden but stays the accessible name.
        className={`relative flex min-h-10 items-center gap-3 rounded-r rounded-l-none px-3 text-sm rail:justify-center rail:px-0 ${active ? "bg-white/10 font-medium text-white before:absolute before:inset-y-0 before:left-0 before:w-[3px] before:bg-gold" : "text-on-dark-muted hover:bg-white/5 hover:text-white"}`}
      >
        <Icon aria-hidden="true" className="size-5 shrink-0" strokeWidth={1.5} />
        <span className="rail:sr-only">{label}</span>
      </Link>
    </Tooltip>
  );
}

/** Up to five recent matters; nothing at all when there are none (Home already says so). */
function ApiRecentMatters() {
  const { matters, failed } = useRecentMatters();
  const t = useTranslations("shell");
  if (failed) {
    return <p className="mt-6 px-3 text-xs text-red-bg rail:hidden">{t("recentLoadFailed")}</p>;
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
    <div className="mt-6 border-t border-white/10 pt-4 rail:hidden">
      <div className="text-on-dark-muted mb-1 px-3 text-xs font-medium">{t("recentMatters")}</div>
      {matters.slice(0, 5).map((matter) => (
        <Link
          key={matter.id}
          href={`/matters/${matter.id}`}
          className="text-on-dark-muted flex min-h-10 items-baseline gap-2 rounded px-3 py-2 text-sm hover:bg-white/5 hover:text-white"
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
