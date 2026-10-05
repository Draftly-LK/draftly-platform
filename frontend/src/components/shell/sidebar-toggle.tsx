"use client";

import { ChevronLeft, ChevronRight } from "lucide-react";
import { useTranslations } from "next-intl";
import { Tooltip } from "@/components/ui/tooltip";
import { useSidebarState } from "./sidebar-state";

/** Vertical centre of the logo row: the sidebar's 12px padding plus half the 64px row. */
const LOGO_ROW_CENTER = 44;
const HIT = 40;

/**
 * The sidebar's collapse button: a 26px round button centred on the sidebar's
 * right edge, half inside and half outside, level with the logo in both states.
 *
 * It lives in the app shell, not in the sidebar, because the sidebar clips its
 * contents (that is how the shared backdrop stays aligned) and would cut off the
 * outer half. It is fixed at `left: --sidebar-width` and transitions with the
 * sidebar's own width, so it slides with the edge. It sits above the sidebar and
 * its shadow (z-30 against the sidebar's z-20). The visible circle is 26px; the
 * button around it is a 40px transparent hit area. Desktop only: below 1024px the
 * sidebar is a drawer and has no collapsed state.
 */
export function SidebarToggle() {
  const t = useTranslations("shell");
  const { collapsed, toggle } = useSidebarState();
  const label = collapsed ? t("expandSidebar") : t("collapseSidebar");
  const Chevron = collapsed ? ChevronRight : ChevronLeft;
  return (
    <Tooltip
      label={label}
      shortcut={t("sidebarShortcut")}
      className="fixed z-30 hidden transition-[left] duration-[180ms] ease-out lg:block"
      style={{ left: `calc(var(--sidebar-width) - ${HIT / 2}px)`, top: LOGO_ROW_CENTER - HIT / 2, width: HIT, height: HIT }}
    >
      <button
        type="button"
        aria-label={label}
        aria-expanded={!collapsed}
        aria-controls="app-sidebar"
        aria-keyshortcuts={"Control+\\"}
        onClick={toggle}
        // The global focus ring would outline the 40px hit area; the ring belongs on the circle.
        className="group grid size-full cursor-pointer place-items-center focus-visible:outline-none"
      >
        <span className="grid size-[26px] place-items-center rounded-full border border-white/[0.22] bg-navy-800 text-on-dark-muted group-hover:border-gold group-hover:text-white group-focus-visible:outline group-focus-visible:outline-2 group-focus-visible:outline-offset-2 group-focus-visible:outline-ring-on-dark">
          <Chevron aria-hidden="true" className="size-[15px]" strokeWidth={1.5} />
        </span>
      </button>
    </Tooltip>
  );
}
