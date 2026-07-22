"use client";

import {
  CircleHelp,
  Clock3,
  FileStack,
  Home,
  Library,
  Menu,
  Plus,
  RotateCcw,
  Settings,
  Workflow,
  X,
} from "lucide-react";
import { useTranslations } from "next-intl";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState } from "react";
import { matters } from "@/lib/mocks";
import { useDemoStore } from "@/lib/store";
import { IconButton } from "@/components/ui/icon-button";
import { CommandPalette } from "./command-palette";

export function Sidebar() {
  const t = useTranslations("shell");
  const app = useTranslations("app");
  const pathname = usePathname();
  const resetDemo = useDemoStore((state) => state.resetDemo);
  const [open, setOpen] = useState(false);
  const links = [
    { href: "/", label: t("home"), icon: Home },
    { href: "/matters", label: t("matters"), icon: FileStack },
    { href: "/workflows", label: t("workflows"), icon: Workflow },
    { href: "/library", label: t("library"), icon: Library },
    { href: "/history", label: t("history"), icon: Clock3 },
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
        className={`border-border bg-canvas fixed inset-y-0 left-0 z-20 flex w-[244px] flex-col border-r p-3 transition-transform md:translate-x-0 ${open ? "translate-x-0" : "-translate-x-full"}`}
      >
        <div className="flex h-12 items-center gap-3 px-2">
          <div
            aria-hidden="true"
            className="border-forest font-heading text-forest grid size-8 place-items-center rounded border-2 text-lg font-semibold"
          >
            D
          </div>
          <div className="min-w-0 flex-1">
            <div className="font-heading text-xl font-semibold">
              {app("name")}
            </div>
            <div className="text-muted-ink truncate text-xs">
              {t("workspace")}
            </div>
          </div>
          <IconButton
            label={t("close")}
            className="md:hidden"
            onClick={() => setOpen(false)}
          >
            <X className="size-5" />
          </IconButton>
        </div>
        <div className="mt-3">
          <CommandPalette />
          <Link
            href="/new"
            className="border-forest bg-forest mt-2 inline-flex min-h-10 w-full items-center justify-center gap-2 rounded border px-3 py-2 font-medium text-white hover:brightness-90"
          >
            <Plus className="size-4" strokeWidth={1.5} />
            {t("create")}
          </Link>
        </div>
        <nav className="mt-4 space-y-1" aria-label={t("workspace")}>
          {links.map(({ href, label, icon: Icon }) => (
            <Link
              key={href}
              href={href}
              onClick={() => setOpen(false)}
              className={`flex min-h-10 items-center gap-3 rounded border-l-2 px-3 ${pathname === href || (href !== "/" && pathname.startsWith(href)) ? "border-forest bg-selected-bg text-forest font-medium" : "hover:bg-hover-bg border-transparent"}`}
            >
              <Icon className="size-5" strokeWidth={1.5} />
              {label}
            </Link>
          ))}
        </nav>
        <div className="border-border mt-5 border-t pt-4">
          <div className="text-muted-ink px-3 text-xs font-semibold uppercase">
            {t("recentMatters")}
          </div>
          {matters.slice(0, 2).map((matter) => (
            <Link
              key={matter.id}
              href={`/matters/${matter.id}`}
              className="hover:bg-hover-bg mt-1 block truncate rounded px-3 py-2 text-sm"
            >
              {matter.reference}
            </Link>
          ))}
        </div>
        <div className="border-border mt-auto space-y-1 border-t pt-3">
          <button
            className="hover:bg-hover-bg flex min-h-10 w-full items-center gap-3 rounded px-3 text-left"
            onClick={resetDemo}
          >
            <RotateCcw className="size-5" strokeWidth={1.5} />
            {t("resetDemo")}
          </button>
          <Link
            className="hover:bg-hover-bg flex min-h-10 items-center gap-3 rounded px-3"
            href="/settings"
          >
            <Settings className="size-5" strokeWidth={1.5} />
            {t("settings")}
          </Link>
          <Link
            className="hover:bg-hover-bg flex min-h-10 items-center gap-3 rounded px-3"
            href="/help"
          >
            <CircleHelp className="size-5" strokeWidth={1.5} />
            {t("help")}
          </Link>
        </div>
      </aside>
    </>
  );
}
