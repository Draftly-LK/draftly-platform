"use client";

import { ChevronLeft, ChevronRight } from "lucide-react";
import { useTranslations } from "next-intl";
import { Tooltip } from "@/components/ui/tooltip";
import { useSidebarState } from "./sidebar-state";

/** Vertical centre of the logo row: the sidebar's 12px padding plus half the 64px row. */
const LOGO_ROW_CENTER = 44;
const HIT = 40;

/**
 * The sidebar's collapse button: a 32px round button centred on the sidebar's
 * right edge, half inside and half outside, level with the logo in both states.
 * It has no resting border (the sidebar has none either); on hover a gold ring
 * shows on its outer (right) half only. The fill matches the sidebar, so the inner
 * half blends into it.
 *
 * It lives in the app shell, not in the sidebar, because the sidebar clips its
 * contents (that is how the shared backdrop stays aligned) and would cut off the
 * outer half. It is fixed at `left: --sidebar-width` and transitions with the
 * sidebar's own width, so it slides with the edge. It sits above the sidebar and
 * its shadow (z-30 against the sidebar's z-20). The visible circle is 32px; the
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
        {/* No resting border, matching the sidebar edge (which has none). On hover a gold ring shows on the outer half only: a full 1px circle on ::before clipped to the right half (a border-right would colour only a quarter of a circle). The fill matches the sidebar backdrop at this spot, so the inner half disappears into it. */}
        <span className="relative grid size-8 place-items-center rounded-full bg-[#1A2F52] text-on-dark-muted before:pointer-events-none before:absolute before:inset-0 before:rounded-full before:border before:border-transparent before:[clip-path:inset(0_0_0_50%)] group-hover:text-white group-hover:before:border-gold group-focus-visible:outline group-focus-visible:outline-2 group-focus-visible:outline-offset-2 group-focus-visible:outline-ring-on-dark">
          <Chevron aria-hidden="true" className="size-4" strokeWidth={1.5} />
        </span>
      </button>
    </Tooltip>
  );
}
