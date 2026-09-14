"use client";

import { MoreHorizontal } from "lucide-react";
import { useTranslations } from "next-intl";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import { IconButton } from "@/components/ui/icon-button";
import { ApiError, isApiEnabled, type TokenProvider } from "@/lib/api/client";
import { getMatter } from "@/lib/api/matters";
import { useTokenProvider } from "@/lib/api/use-token-provider";
import { familyLabelKey, subtypeLabelKey } from "@/lib/rta/taxonomy";
import { useDemoStore } from "@/lib/store";
import type { ApiRtaMatter, RtaMatterState } from "@/types/rta";
import { LocaleToggle } from "./locale-toggle";
import { STAGE_ORDER, stageForState } from "./matter-stage";

const NAV_TABS = [
  "overview",
  "documents",
  "facts",
  "checks",
  "missingDocuments",
  "drafts",
  "exports",
  "assistantTab",
] as const;

const NAV_HREF: Record<(typeof NAV_TABS)[number], (id: string) => string> = {
  overview: (id) => `/matters/${id}`,
  documents: (id) => `/matters/${id}/documents`,
  facts: (id) => `/matters/${id}/facts`,
  checks: (id) => `/matters/${id}/checks`,
  missingDocuments: (id) => `/matters/${id}/missing-documents`,
  drafts: (id) => `/matters/${id}/drafts`,
  exports: (id) => `/matters/${id}/exports`,
  assistantTab: (id) => `/matters/${id}/assistant`,
};

interface HeaderData {
  reference: string;
  subtitleKey: string | null;
  subtitleFallback: string;
  state: RtaMatterState | null;
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

function ApiBoundMatterHeader({ matterId }: { matterId: string }) {
  const getToken = useTokenProvider();
  const [matter, setMatter] = useState<ApiRtaMatter | null>(null);
  const [error, setError] = useState<string | null>(null);
  const t = useTranslations("matterNav");

  useEffect(() => {
    let cancelled = false;
    setError(null);
    fetchMatter(getToken, matterId)
      .then((result) => {
        if (!cancelled) setMatter(result);
      })
      .catch((cause: unknown) => {
        if (!cancelled) setError(cause instanceof ApiError ? cause.message : t("loadError"));
      });
    return () => {
      cancelled = true;
    };
  }, [getToken, matterId, t]);

  if (error) {
    return (
      <MatterHeaderShell
        matterId={matterId}
        data={{ reference: matterId, subtitleKey: null, subtitleFallback: error, state: null }}
      />
    );
  }
  if (!matter) return null;

  const labelKey = matter.subtypeId
    ? subtypeLabelKey(matter.subtypeId)
    : matter.familyId
      ? familyLabelKey(matter.familyId)
      : null;

  return (
    <MatterHeaderShell
      matterId={matterId}
      data={{
        reference: matter.reference,
        subtitleKey: labelKey ?? null,
        subtitleFallback: matter.subtypeId ?? matter.familyId ?? t("type"),
        state: matter.state,
      }}
    />
  );
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
      data={{
        reference: matter.reference,
        subtitleKey: null,
        subtitleFallback: matter.parties.map((party) => party.nameToken).join(" ↔ "),
        state: null,
      }}
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
  data: HeaderData;
  updatedAt?: string;
}) {
  const t = useTranslations("matterNav");
  /** `subtitleKey` is a rule-pack key (`rta.subtype.*`, `rta.family.*`), which
   *  lives at the message root — resolving it through the namespaced `t` above
   *  asked for `matterNav.rta.subtype.…` and rendered the raw key. */
  const tRoot = useTranslations();
  const pathname = usePathname();

  return (
    <header className="border-border bg-surface border-b">
      <div className="flex min-h-24 items-start gap-4 px-6 py-4">
        <div className="min-w-0 flex-1">
          <div className="text-muted-ink flex flex-wrap items-center gap-2 text-xs">
            <span className="border-border-strong rounded-full border px-2 py-1">
              {t("regime")}
            </span>
            <span>{data.subtitleKey ? tRoot(data.subtitleKey) : data.subtitleFallback}</span>
            {data.state && (
              <>
                <span>·</span>
                <span>{t(`stateLabel.${data.state}`)}</span>
              </>
            )}
          </div>
          <h1 className="mt-1 truncate text-2xl font-semibold">{data.reference}</h1>
          {updatedAt && (
            <div className="text-muted-ink mt-1 truncate text-sm">
              {t("updated", { date: updatedAt })}
            </div>
          )}
        </div>
        <div className="flex shrink-0 items-center gap-2">
          <LocaleToggle />
          <IconButton label={t("menu")}>
            <MoreHorizontal className="size-5" strokeWidth={1.5} />
          </IconButton>
        </div>
      </div>
      {data.state && <MatterStageStepper state={data.state} />}
      <nav aria-label={data.reference} className="flex min-w-0 overflow-x-auto px-4">
        {NAV_TABS.map((tab) => {
          const href = NAV_HREF[tab](matterId);
          const active = pathname === href || pathname.startsWith(`${href}/`);
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

/** The visible RtaMatterState progression: which of the six demo stages is current. */
function MatterStageStepper({ state }: { state: RtaMatterState }) {
  const t = useTranslations("matterNav.stage");
  const current = stageForState(state);
  return (
    <ol className="text-muted-ink flex min-w-0 gap-1 overflow-x-auto px-6 pb-2 text-xs">
      {STAGE_ORDER.map((stage, index) => {
        const currentIndex = STAGE_ORDER.indexOf(current);
        const done = index < currentIndex;
        const active = stage === current;
        return (
          <li
            key={stage}
            aria-current={active ? "step" : undefined}
            className={`shrink-0 rounded-full border px-2 py-1 ${
              active
                ? "border-forest text-forest font-medium"
                : done
                  ? "border-border-strong text-ink"
                  : "border-border text-muted-ink"
            }`}
          >
            {t(stage)}
          </li>
        );
      })}
    </ol>
  );
}
