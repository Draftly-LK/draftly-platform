"use client";

import { ChevronLeft, ChevronRight, FileText } from "lucide-react";
import { useTranslations } from "next-intl";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";
import { isApiEnabled, type TokenProvider, apiErrorMessage } from "@/lib/api/client";
import { getMatter } from "@/lib/api/matters";
import { useTokenProvider } from "@/lib/api/use-token-provider";
import { useDemoStore } from "@/lib/store";
import { cn } from "@/lib/utils";
import { segmentedOption, segmentedTrack } from "@/components/ui/segmented-control";
import type { ApiRtaMatter, RtaMatterState } from "@/types/rta";
import { MATTER_SECTIONS, matterSectionHref, sectionForPath } from "./matter-sections";
import { MatterStepper } from "./matter-stepper";


interface HeaderData {
  reference: string;
  state: RtaMatterState | null;
  /** Why the matter could not be loaded, shown under the title. */
  error?: string;
}

/**
 * `useTokenProvider` calls Clerk's `useAuth`, which requires a `ClerkProvider`
 * not mounted in the offline demo. `isApiEnabled()` reads a build-time env var
 * (stable across renders), so splitting into two components keeps hook order
 * stable per the pattern already used by `new-matter-screen.tsx`.
 */
export function MatterHeader({ matterId }: { matterId: string }) {
  return isApiEnabled() ? (
    <ApiBoundMatterHeader matterId={matterId} />
  ) : (
    <DemoMatterHeader matterId={matterId} />
  );
}

/**
 * The last matter each header loaded. Every tab is its own page, so without
 * this the header would vanish and reload on each tab switch; with it the
 * header paints at once and refreshes quietly behind.
 */
const matterCache = new Map<string, ApiRtaMatter>();

function ApiBoundMatterHeader({ matterId }: { matterId: string }) {
  const getToken = useTokenProvider();
  const [matter, setMatter] = useState<ApiRtaMatter | null>(() => matterCache.get(matterId) ?? null);
  const [error, setError] = useState<string | null>(null);
  const t = useTranslations("matterNav");

  useEffect(() => {
    let cancelled = false;
    setError(null);
    setMatter(matterCache.get(matterId) ?? null);
    fetchMatter(getToken, matterId)
      .then((result) => {
        matterCache.set(matterId, result);
        if (!cancelled) setMatter(result);
      })
      .catch((cause: unknown) => {
        if (!cancelled) setError(apiErrorMessage(cause, t("loadError")));
      });
    return () => {
      cancelled = true;
    };
  }, [getToken, matterId, t]);

  if (error) {
    return (
      <MatterHeaderShell
        matterId={matterId}
        data={{ reference: matterId, state: null, error }}
      />
    );
  }
  // First visit: hold the header's space so the page below does not jump when it arrives.
  return <MatterHeaderShell matterId={matterId} data={matter ? { reference: matter.reference, state: matter.state } : null} />;
}

function fetchMatter(getToken: TokenProvider, matterId: string): Promise<ApiRtaMatter> {
  return getMatter(getToken, matterId);
}

function DemoMatterHeader({ matterId }: { matterId: string }) {
  const matter = useDemoStore((state) => state.matters.find((item) => item.id === matterId));
  if (!matter) return null;
  return (
    <MatterHeaderShell
      matterId={matterId}
      data={{ reference: matter.reference, state: null }}
      updatedAt={matter.updatedAt.slice(0, 10)}
    />
  );
}

function MatterHeaderShell({
  matterId,
  data,
  updatedAt,
}: {
  matterId: string;
  /** Null while the matter is first loading. */
  data: HeaderData | null;
  updatedAt?: string;
}) {
  const t = useTranslations("matterNav");

  return (
    <header data-matter-header className="border-border bg-surface border-b">
      {/* pl-16 below lg keeps the title clear of the fixed mobile menu button. */}
      <div className="flex items-center gap-4 pb-3 pl-16 pr-6 pt-5 lg:pl-6">
        <span className="bg-surface-inverse text-gold hidden size-12 shrink-0 place-items-center rounded-lg sm:grid" aria-hidden="true">
          <FileText className="size-6" strokeWidth={1.5} />
        </span>
        <div className="min-w-0 flex-1">
          {data ? (
            <h1 className="font-display text-2xl font-semibold leading-tight tabular-nums [overflow-wrap:anywhere] sm:truncate sm:text-3xl">
              {data.reference}
            </h1>
          ) : (
            <div aria-hidden="true" className="bg-disabled-bg h-8 w-56 max-w-full animate-pulse rounded-control motion-reduce:animate-none sm:h-9" />
          )}
          {data?.error && <p role="alert" className="text-red mt-0.5 text-sm">{data.error}</p>}
          {updatedAt && (
            <div className="text-muted-ink mt-0.5 truncate text-sm">
              {t("updated", { date: updatedAt })}
            </div>
          )}
        </div>
      </div>
      {data?.state ? (
        <MatterStepper state={data.state} />
      ) : data === null ? (
        <div aria-hidden="true" className="h-[68px] sm:h-[76px]" />
      ) : null}
      <MatterTabs matterId={matterId} label={data?.reference ?? matterId} />
    </header>
  );
}

const SCROLL_STEP = 240;

/**
 * The matter's sections in the same segmented pill as the Matters filters and
 * the Legal sources toggle. When they do not fit, the pill scrolls sideways
 * without a visible scrollbar, round arrow buttons sit either side of it (the
 * one for an end already reached is dimmed), and the current section is
 * brought into view.
 */
function MatterTabs({ matterId, label }: { matterId: string; label: string }) {
  const t = useTranslations("matterNav");
  const pathname = usePathname();
  const ref = useRef<HTMLDivElement>(null);
  const [scroll, setScroll] = useState({ overflow: false, start: false, end: false });

  const measure = useCallback(() => {
    const strip = ref.current;
    if (!strip) return;
    setScroll({
      overflow: strip.scrollWidth > strip.clientWidth + 1,
      start: strip.scrollLeft > 4,
      end: strip.scrollLeft + strip.clientWidth < strip.scrollWidth - 4,
    });
  }, []);

  /** Centre the current section, or (`nudge`) only move enough to show it whole. */
  const reveal = useCallback(
    (nudge: boolean) => {
      const strip = ref.current;
      const active = strip?.querySelector<HTMLElement>('[aria-current="page"]');
      if (!strip || !active) return;
      const left = active.offsetLeft;
      const right = left + active.offsetWidth;
      if (!nudge) strip.scrollLeft = left - (strip.clientWidth - active.offsetWidth) / 2;
      else if (left < strip.scrollLeft) strip.scrollLeft = left - 8;
      else if (right > strip.scrollLeft + strip.clientWidth) strip.scrollLeft = right - strip.clientWidth + 8;
      measure();
    },
    [measure],
  );

  // Widths settle late (the arrows appearing, web fonts arriving), so keep the
  // current section whole whenever they change, not only on the first paint.
  useEffect(() => {
    const strip = ref.current;
    if (!strip) return;
    const settle = () => reveal(true);
    const observer = typeof ResizeObserver === "function" ? new ResizeObserver(settle) : null;
    observer?.observe(strip);
    if (strip.firstElementChild) observer?.observe(strip.firstElementChild);
    void document.fonts?.ready.then(settle);
    return () => observer?.disconnect();
  }, [reveal]);

  useEffect(() => {
    reveal(false);
  }, [reveal, pathname, scroll.overflow]);

  const scrollBy = (direction: 1 | -1) => ref.current?.scrollBy({ left: direction * SCROLL_STEP, behavior: "smooth" });

  return (
    <nav aria-label={label} className="flex items-center justify-center gap-2 px-4 pb-4 pt-1 lg:px-6">
      {/* Shortcuts for the swipe; tabbing through the links still reaches every section. */}
      {scroll.overflow ? <ScrollButton side="start" label={t("tabsBack")} disabled={!scroll.start} onClick={() => scrollBy(-1)} /> : null}
      <div
        ref={ref}
        onScroll={measure}
        // `relative` makes the strip the pills' offset parent, so centring the current one measures from the strip.
        className={cn(segmentedTrack, "relative min-w-0 overflow-x-auto [scrollbar-width:none] [&::-webkit-scrollbar]:hidden")}
      >
        {MATTER_SECTIONS.map((tab) => {
          const href = matterSectionHref(tab, matterId);
          const active = sectionForPath(pathname, matterId) === tab;
          return (
            <Link key={tab} href={href} aria-current={active ? "page" : undefined} className={cn(segmentedOption(active), "shrink-0")}>
              {t(tab)}
            </Link>
          );
        })}
        {/* A scrolled strip drops its end padding, which let the rounded end clip the last pill. */}
        <span aria-hidden="true" className="w-0.5 shrink-0" />
      </div>
      {scroll.overflow ? <ScrollButton side="end" label={t("tabsMore")} disabled={!scroll.end} onClick={() => scrollBy(1)} /> : null}
    </nav>
  );
}

function ScrollButton({ side, label, disabled, onClick }: { side: "start" | "end"; label: string; disabled: boolean; onClick: () => void }) {
  const Icon = side === "start" ? ChevronLeft : ChevronRight;
  return (
    <button
      type="button"
      tabIndex={-1}
      aria-label={label}
      disabled={disabled}
      onClick={onClick}
      className="border-border-strong bg-surface text-ink hover:bg-hover-bg grid size-8 shrink-0 place-items-center rounded-full border transition-opacity duration-150 disabled:cursor-default disabled:opacity-40 disabled:hover:bg-surface motion-reduce:transition-none"
    >
      <Icon aria-hidden="true" className="size-4" strokeWidth={1.5} />
    </button>
  );
}
