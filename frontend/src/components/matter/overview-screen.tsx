"use client";

import {
  ArrowRight,
  FileCheck2,
  FileText,
  ListChecks,
  ShieldCheck,
} from "lucide-react";
import { useTranslations } from "next-intl";
import Link from "next/link";
import { MatterDashboard } from "@/components/matter/matter-dashboard";
import { isApiEnabled } from "@/lib/api/client";
import { useDemoStore } from "@/lib/store";
import { AppShell } from "@/components/shell/app-shell";

/**
 * The matter dashboard.
 *
 * With the backend configured this reads the live matter; the demo dataset
 * implementation below it is what the offline demo still runs on.
 */
export function OverviewScreen({ matterId }: { matterId: string }) {
  return isApiEnabled() ? (
    <MatterDashboard matterId={matterId} />
  ) : (
    <DemoOverviewScreen matterId={matterId} />
  );
}

function DemoOverviewScreen({ matterId }: { matterId: string }) {
  const t = useTranslations("overview");
  const matter = useDemoStore((state) =>
    state.matters.find((item) => item.id === matterId),
  );
  const allDocuments = useDemoStore((state) => state.documents);
  const allFacts = useDemoStore((state) => state.facts);
  const allChecks = useDemoStore((state) => state.checks);
  const allDrafts = useDemoStore((state) => state.drafts);
  const documents = allDocuments.filter((item) => item.matterId === matterId);
  const facts = allFacts.filter((item) => item.matterId === matterId);
  const checks = allChecks.filter((item) => item.matterId === matterId);
  const drafts = allDrafts.filter((item) => item.matterId === matterId);
  // The workspace views still read the demo dataset, so a matter created
  // against the live API has no local record. Rendering nothing made that look
  // like a broken page; say what happened instead.
  if (!matter) return <MatterNotInWorkspace matterId={matterId} />;
  const progress = [
    { key: "examination", value: matter.progress.examination },
    { key: "drafting", value: matter.progress.drafting },
    { key: "execution", value: matter.progress.execution },
    { key: "attestation", value: matter.progress.attestation },
  ] as const;
  const rows = [
    {
      key: "documents",
      body: t("readyCount", {
        // §10.2: only a completed server processing run counts as ready.
        ready: documents.filter((item) => item.processingState === "PROCESSED")
          .length,
        total: documents.length,
      }),
      href: `/matters/${matterId}/documents`,
      icon: FileText,
    },
    {
      key: "issues",
      body: t("issueCount", {
        count: checks.filter((check) => check.status !== "pass").length,
      }),
      href: `/matters/${matterId}/checks`,
      icon: ListChecks,
    },
    {
      key: "facts",
      body: t("verifiedCount", {
        count: facts.filter((fact) =>
          ["verified", "corrected"].includes(fact.verificationState),
        ).length,
      }),
      href: `/matters/${matterId}/facts`,
      icon: ShieldCheck,
    },
    {
      key: "drafts",
      body: t("draftCount", { count: drafts.length }),
      href: `/matters/${matterId}/drafts`,
      icon: FileCheck2,
    },
  ] as const;
  return (
    <AppShell matterId={matterId}>
      <div className="p-6">
        <section className="border-border bg-surface rounded-card overflow-hidden border">
          <div className="grid gap-6 p-6 lg:grid-cols-[1fr_1.2fr]">
            <div>
              <div className="text-muted-ink text-xs font-semibold">
                {t("activeFunction")}
              </div>
              <h2 className="mt-1 text-3xl font-semibold">
                {t("examination")}
              </h2>
              <div className="border-gold bg-canvas mt-5 rounded border-l-[3px] p-4">
                <div className="text-forest text-xs font-semibold">
                  {t("nextAction")}
                </div>
                <div className="font-heading mt-1 text-xl font-semibold">
                  {t("nextActionBody")}
                </div>
                <Link
                  href={`/matters/${matterId}/facts`}
                  className="border-forest bg-forest mt-3 inline-flex min-h-10 items-center gap-2 rounded-control border px-3 py-2 font-medium text-white"
                >
                  {t("continue")}
                  <ArrowRight className="size-4" strokeWidth={1.5} />
                </Link>
              </div>
            </div>
            <div>
              <div className="text-muted-ink text-xs font-semibold">
                {t("completion")}
              </div>
              <div className="mt-3 space-y-4">
                {progress.map((item) => (
                  <div key={item.key}>
                    <div className="mb-1 flex justify-between text-sm">
                      <span>{t(item.key)}</span>
                      <span className="text-muted-ink tabular-nums">
                        {item.value}%
                      </span>
                    </div>
                    <div className="bg-disabled-bg h-2 rounded-full">
                      <div
                        className="bg-forest h-2 rounded-full"
                        style={{ width: `${item.value}%` }}
                      />
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </section>
        <div className="divide-border border-border bg-surface mt-6 divide-y border-y">
          {rows.map(({ key, body, href, icon: Icon }) => (
            <Link
              href={href}
              key={key}
              className="hover:bg-hover-bg grid min-h-20 grid-cols-[auto_1fr_auto] items-center gap-4 px-4"
            >
              <Icon className="text-forest size-5" strokeWidth={1.5} />
              <div>
                <h2 className="font-heading text-xl font-semibold">{t(key)}</h2>
                <p className="text-muted-ink text-sm">{body}</p>
              </div>
              <span className="text-forest flex items-center gap-2 font-medium">
                {t("view", { section: t(key).toLowerCase() })}
                <ArrowRight className="size-4" strokeWidth={1.5} />
              </span>
            </Link>
          ))}
          <Link
            href={`/matters/${matterId}/activity`}
            className="hover:bg-hover-bg grid min-h-20 grid-cols-[auto_1fr_auto] items-center gap-4 px-4"
          >
            <ShieldCheck className="text-forest size-5" strokeWidth={1.5} />
            <div>
              <h2 className="font-heading text-xl font-semibold">
                {t("activity")}
              </h2>
              <p className="text-muted-ink text-sm">{t("activityBody")}</p>
            </div>
            <ArrowRight className="size-4" strokeWidth={1.5} />
          </Link>
        </div>
      </div>
    </AppShell>
  );
}

/**
 * Shown when the id in the URL is not in the demo dataset.
 *
 * Only reachable on the offline demo path now: with the backend configured the
 * screen above reads the real matter instead.
 */
function MatterNotInWorkspace({ matterId }: { matterId: string }) {
  const t = useTranslations("overview");
  return (
    <AppShell>
      <div className="mx-auto max-w-2xl p-6">
        <div className="border-border bg-surface rounded-card border p-6">
          <h1 className="text-2xl font-semibold">{t("notLoadedTitle")}</h1>
          <p className="text-muted-ink mt-2">{t("notLoadedBody")}</p>
          <p className="text-muted-ink mt-4 font-mono text-xs">{matterId}</p>
          <Link
            href="/matters"
            className="text-forest mt-4 inline-flex items-center gap-2 font-medium hover:underline"
          >
            {t("notLoadedAction")}
            <ArrowRight className="size-4" strokeWidth={1.5} />
          </Link>
        </div>
      </div>
    </AppShell>
  );
}
