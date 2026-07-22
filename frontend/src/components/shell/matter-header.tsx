"use client";

import { MoreHorizontal } from "lucide-react";
import { useTranslations } from "next-intl";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useDemoStore } from "@/lib/store";
import { IconButton } from "@/components/ui/icon-button";
import { LocaleToggle } from "./locale-toggle";

const tabs = [
  "overview",
  "documents",
  "facts",
  "workflow",
  "checks",
  "drafts",
  "activity",
] as const;

export function MatterHeader({ matterId }: { matterId: string }) {
  const t = useTranslations("matterNav");
  const pathname = usePathname();
  const matter = useDemoStore((state) =>
    state.matters.find((item) => item.id === matterId),
  );
  if (!matter) return null;
  return (
    <header className="border-border bg-surface border-b">
      <div className="flex min-h-24 items-start gap-4 px-6 py-4">
        <div className="min-w-0 flex-1">
          <div className="text-muted-ink flex flex-wrap items-center gap-2 text-xs">
            <span className="border-border-strong rounded-full border px-2 py-1">
              {t("regime")}
            </span>
            <span>{t("type")}</span>
            <span>·</span>
            <span>{t("status")}</span>
          </div>
          <h1 className="mt-1 truncate text-2xl font-semibold">
            {matter.reference}
          </h1>
          <div className="text-muted-ink mt-1 truncate text-sm">
            {matter.parties.map((party) => party.nameToken).join(" ↔ ")} ·{" "}
            {t("updated", {
              date: matter.updatedAt.slice(0, 10),
            })}
          </div>
        </div>
        <div className="flex shrink-0 items-center gap-2">
          <LocaleToggle />
          <IconButton label={t("menu")}>
            <MoreHorizontal className="size-5" strokeWidth={1.5} />
          </IconButton>
        </div>
      </div>
      <nav
        aria-label={matter.reference}
        className="flex min-w-0 overflow-x-auto px-4"
      >
        {tabs.map((tab) => {
          const href =
            tab === "overview"
              ? `/matters/${matterId}`
              : `/matters/${matterId}/${tab}`;
          const active =
            pathname === href ||
            (tab === "drafts" && pathname.startsWith(`${href}/`));
          return (
            <Link
              key={tab}
              href={href}
              className={`min-h-11 shrink-0 border-b-2 px-3 py-3 text-sm font-medium ${active ? "border-forest text-forest" : "text-muted-ink hover:text-ink border-transparent"}`}
            >
              {t(tab)}
            </Link>
          );
        })}
      </nav>
    </header>
  );
}
