"use client";

import { FilePlus2 } from "lucide-react";
import { useTranslations } from "next-intl";
import Link from "next/link";
import { buttonClass } from "@/components/ui/button";
import { cn } from "@/lib/utils";

/**
 * "Create a matter": the one way to start a matter, with the same label and icon
 * everywhere (dashboard header, Matters page). It is the shared primary button
 * style, so it looks identical on navy and on white.
 */
export function CreateMatterLink({ className }: { className?: string }) {
  const t = useTranslations("home");
  return (
    <Link href="/new" className={cn(buttonClass("primary"), className)}>
      <FilePlus2 aria-hidden="true" className="size-4" strokeWidth={1.5} />
      {t("createTitle")}
    </Link>
  );
}
