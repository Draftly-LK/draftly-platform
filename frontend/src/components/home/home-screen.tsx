import {
  ArrowRight,
  CalendarClock,
  FilePlus2,
  MessageSquareText,
} from "lucide-react";
import { getFormatter, getTranslations } from "next-intl/server";
import Link from "next/link";
import { demoOnly, obligations as obligationFixtures } from "@/lib/mocks";
import { CommonWorkflows } from "@/components/home/common-workflows";
import { RecentMatters } from "@/components/home/recent-matters";
import { AppShell } from "@/components/shell/app-shell";
import { PageHeader } from "@/components/shell/page-header";

export async function HomeScreen() {
  const t = await getTranslations("home");
  const to = await getTranslations("obligations");
  // Fixture deadlines are demo-only; with the API configured there are none to show.
  const obligations = demoOnly(obligationFixtures);
  const format = await getFormatter();
  const actions = [
    {
      href: "/new",
      title: t("createTitle"),
      body: t("createBody"),
      icon: FilePlus2,
    },
    {
      href: "/assistant",
      title: t("askTitle"),
      body: t("askBody"),
      icon: MessageSquareText,
    },
  ];
  return (
    <AppShell>
      <PageHeader title={t("title")} description={t("description")} />
      <div className="mx-auto max-w-6xl p-6">
        <section
          aria-labelledby="command-title"
          className="border-border border-b pb-8"
        >
          <h2 id="command-title" className="text-2xl font-semibold">
            {t("commandTitle")}
          </h2>
          <div className="border-border-strong bg-surface mt-4 grid overflow-hidden rounded border md:grid-cols-2">
            {actions.map(({ href, title, body, icon: Icon }, index) => (
              <Link
                href={href}
                key={href}
                className={`hover:bg-hover-bg group flex min-h-28 items-center gap-4 p-5 ${index > 0 ? "border-border border-t md:border-l md:border-t-0" : ""}`}
              >
                <span className="bg-selected-bg text-forest grid size-10 shrink-0 place-items-center rounded">
                  <Icon className="size-5" strokeWidth={1.5} />
                </span>
                <span className="min-w-0 flex-1">
                  <span className="block font-semibold">{title}</span>
                  <span className="text-muted-ink mt-1 block text-sm">
                    {body}
                  </span>
                </span>
                <ArrowRight
                  className="text-muted-ink group-hover:text-forest size-4 shrink-0"
                  strokeWidth={1.5}
                />
              </Link>
            ))}
          </div>
        </section>
        <section
          aria-labelledby="recent-title"
          className="border-border border-b py-8"
        >
          <div className="flex items-center justify-between gap-4">
            <h2 id="recent-title" className="text-2xl font-semibold">
              {t("recentTitle")}
            </h2>
            <Link
              href="/matters"
              className="text-teal font-medium hover:underline"
            >
              {t("viewAll")}
            </Link>
          </div>
          <div className="border-border-strong bg-surface mt-3 overflow-hidden rounded border">
            <RecentMatters />
          </div>
        </section>
        <CommonWorkflows />
        {obligations.length > 0 && (
          <section aria-labelledby="obligations-title" className="py-8">
            <h2 id="obligations-title" className="text-2xl font-semibold">
              {t("obligationsTitle")}
            </h2>
            <div className="divide-border border-border mt-3 divide-y border-y">
              {obligations.map((obligation) => (
                <div
                  key={obligation.id}
                  className="flex min-h-14 items-center gap-3 px-2"
                >
                  <CalendarClock
                    className="text-muted-ink size-4"
                    strokeWidth={1.5}
                  />
                  <span className="min-w-0 flex-1 font-medium">
                    {to(
                      obligation.labelKey.split(".").at(-1) as
                        | "monthlyList"
                        | "licenseRenewal"
                        | "lawyerReview",
                    )}
                  </span>
                  <span className="text-muted-ink text-sm tabular-nums">
                    {t("due", {
                      date: format.dateTime(
                        new Date(`${obligation.dueDate}T00:00:00Z`),
                        { day: "numeric", month: "short", year: "numeric" },
                      ),
                    })}
                  </span>
                </div>
              ))}
            </div>
          </section>
        )}
      </div>
    </AppShell>
  );
}
