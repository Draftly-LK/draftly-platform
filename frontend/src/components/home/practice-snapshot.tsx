"use client";

import { FilePenLine, FolderOpen, UserRoundCheck } from "lucide-react";
import { useTranslations } from "next-intl";
import { isApiEnabled } from "@/lib/api/client";
import { useRecentMatters } from "@/lib/api/use-recent-matters";
import { summarizeMatters, type PracticeSnapshot as Snapshot } from "@/lib/home/practice-snapshot";
import type { ApiRtaMatter } from "@/types/rta";
import { demoMatterFeed } from "./recent-matters";

/** The hero's at-a-glance counts, from the same feed as "Recent matters". */
export function PracticeSnapshot() {
  return isApiEnabled() ? <ApiPracticeSnapshot /> : <SnapshotPanel matters={demoMatterFeed()} loading={false} />;
}

function ApiPracticeSnapshot() {
  const { matters, loading, failed } = useRecentMatters();
  return <SnapshotPanel matters={matters} loading={loading} failed={failed} />;
}

function SnapshotPanel({
  matters,
  loading,
  failed = false,
}: {
  matters: ApiRtaMatter[];
  loading: boolean;
  failed?: boolean;
}) {
  const t = useTranslations("home.snapshot");
  const summary: Snapshot | null = loading || failed ? null : summarizeMatters(matters.map((matter) => matter.state));
  const stats = [
    { key: "open", icon: FolderOpen, value: summary?.open },
    { key: "needsReview", icon: UserRoundCheck, value: summary?.needsReview },
    { key: "drafting", icon: FilePenLine, value: summary?.drafting },
  ] as const;
  return (
    <section
      aria-labelledby="snapshot-title"
      className="rounded-card border border-white/10 bg-white/[0.04] p-5 backdrop-blur-sm"
    >
      <h2 id="snapshot-title" className="text-on-dark-muted text-xs font-semibold uppercase tracking-[0.1em]">
        {t("title")}
      </h2>
      <dl className="mt-4 grid grid-cols-3 gap-3">
        {stats.map(({ key, icon: Icon, value }) => (
          <div key={key} className="rounded border border-white/10 bg-white/[0.03] p-3">
            <dt className="text-on-dark-muted flex min-h-8 items-start gap-1.5 text-xs leading-snug">
              <Icon className="mt-px size-4 shrink-0" strokeWidth={1.5} aria-hidden="true" />
              <span>{t(key)}</span>
            </dt>
            <dd className="font-display mt-2 text-[32px] font-semibold leading-none text-white tabular-nums">
              {value ?? "—"}
            </dd>
          </div>
        ))}
      </dl>
      {failed && <p className="text-red-bg mt-3 text-xs">{t("failed")}</p>}
    </section>
  );
}
