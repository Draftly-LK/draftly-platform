"use client";

import { CircleHelp, Clock3, FileStack, Home, Library, Menu, Plus, RotateCcw, Settings, Workflow, X } from "lucide-react";
import { useTranslations } from "next-intl";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState } from "react";
import { matters } from "@/lib/mocks";
import { useDemoStore } from "@/lib/store";
import { Button } from "@/components/ui/button";
import { IconButton } from "@/components/ui/icon-button";
import { CommandPalette } from "./command-palette";

export function Sidebar() {
  const t = useTranslations("shell");
  const pathname = usePathname();
  const resetDemo = useDemoStore((state) => state.resetDemo);
  const [open, setOpen] = useState(false);
  const links = [
    { href: "/", label: t("home"), icon: Home }, { href: "/matters", label: t("matters"), icon: FileStack },
    { href: "/workflows", label: t("workflows"), icon: Workflow }, { href: "/library", label: t("library"), icon: Library }, { href: "/history", label: t("history"), icon: Clock3 }
  ];
  return <><div className="fixed left-3 top-3 z-20 md:hidden"><IconButton label={t("openNavigation")} className="border-border-strong bg-surface" onClick={() => setOpen(true)}><Menu className="size-5" strokeWidth={1.5} /></IconButton></div>{open && <button aria-label={t("close")} className="fixed inset-0 z-20 bg-ink/25 md:hidden" onClick={() => setOpen(false)} />}<aside data-app-chrome className={`fixed inset-y-0 left-0 z-20 flex w-[244px] flex-col border-r border-border bg-canvas p-3 transition-transform md:translate-x-0 ${open ? "translate-x-0" : "-translate-x-full"}`}><div className="flex h-12 items-center gap-3 px-2"><div aria-hidden="true" className="grid size-8 place-items-center rounded border-2 border-forest font-heading text-lg font-semibold text-forest">D</div><div className="min-w-0 flex-1"><div className="font-heading text-xl font-semibold">Draftly</div><div className="truncate text-xs text-muted-ink">{t("workspace")}</div></div><IconButton label={t("close")} className="md:hidden" onClick={() => setOpen(false)}><X className="size-5" /></IconButton></div><div className="mt-3"><CommandPalette /><Link href="/new"><Button variant="primary" className="mt-2 w-full"><Plus className="size-4" strokeWidth={1.5} />{t("create")}</Button></Link></div><nav className="mt-4 space-y-1" aria-label={t("workspace")}>{links.map(({ href, label, icon: Icon }) => <Link key={href} href={href} onClick={() => setOpen(false)} className={`flex min-h-10 items-center gap-3 rounded border-l-2 px-3 ${pathname === href || (href !== "/" && pathname.startsWith(href)) ? "border-forest bg-selected-bg font-medium text-forest" : "border-transparent hover:bg-hover-bg"}`}><Icon className="size-5" strokeWidth={1.5} />{label}</Link>)}</nav><div className="mt-5 border-t border-border pt-4"><div className="px-3 text-xs font-semibold uppercase text-muted-ink">{t("recentMatters")}</div>{matters.slice(0, 2).map((matter) => <Link key={matter.id} href={`/matters/${matter.id}`} className="mt-1 block truncate rounded px-3 py-2 text-sm hover:bg-hover-bg">{matter.reference}</Link>)}</div><div className="mt-auto space-y-1 border-t border-border pt-3"><button className="flex min-h-10 w-full items-center gap-3 rounded px-3 text-left hover:bg-hover-bg" onClick={resetDemo}><RotateCcw className="size-5" strokeWidth={1.5} />{t("resetDemo")}</button><Link className="flex min-h-10 items-center gap-3 rounded px-3 hover:bg-hover-bg" href="/settings"><Settings className="size-5" strokeWidth={1.5} />{t("settings")}</Link><Link className="flex min-h-10 items-center gap-3 rounded px-3 hover:bg-hover-bg" href="/help"><CircleHelp className="size-5" strokeWidth={1.5} />{t("help")}</Link></div></aside></>;
}

