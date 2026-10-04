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
import { PracticeSnapshot } from "@/components/home/practice-snapshot";
import { RecentMatters } from "@/components/home/recent-matters";
import { AppShell } from "@/components/shell/app-shell";
import { HeaderUserButton } from "@/components/shell/user-button";

export async function HomeScreen() {
  const t = await getTranslations("home");
  const to = await getTranslations("obligations");
  // Fixture deadlines are demo-only; with the API configured there are none to show.
  const obligations = demoOnly(obligationFixtures);
  const format = await getFormatter();
  return (
    <AppShell>
      <section
        aria-labelledby="home-title"
        data-surface="inverse"
        className="bg-navy-900 border-gold relative isolate overflow-hidden border-b-2 text-white"
      >
        {/* Home has no page header, so the profile button sits where the page
            header puts it on every other screen: top-right, 24px in. The grid
            keeps clear of it (right padding on wide screens, top padding on
            narrow ones) so it never covers the practice snapshot. On wide
            screens the snapshot's top edge lines up with the photo's (lg:pt-7
            = top-6 plus the button's 4px padding). */}
        <div className="absolute right-6 top-6 z-10 [&_a:hover]:bg-white/10">
          <HeaderUserButton />
        </div>
        <div className="grid items-end gap-8 px-6 pb-9 pt-24 md:pt-8 lg:pt-7 lg:grid-cols-[minmax(0,1fr)_440px] lg:pr-28">
          <div>
            <p className="text-gold text-xs font-semibold">
              {t("eyebrow")}
            </p>
            <h1
              id="home-title"
              className="font-display mt-3 text-3xl font-semibold leading-[1.05]"
            >
              {t("title")}
            </h1>
            <p className="text-on-dark-muted mt-3 max-w-xl text-lg">
              {t("description")}
            </p>
            {/* Equal-width buttons: auto-cols-fr sizes both columns to the
                wider label; on phones they stack full width. */}
            <div className="mt-7 grid gap-3 sm:inline-grid sm:auto-cols-fr sm:grid-flow-col">
              <Link
                href="/new"
                className="bg-gold text-navy-950 rounded-control inline-flex min-h-11 items-center justify-center gap-2 px-4 font-semibold hover:bg-gold-hover"
              >
                <FilePlus2
                  className="size-4"
                  strokeWidth={1.5}
                  aria-hidden="true"
                />
                {t("createTitle")}
              </Link>
              <Link
                href="/assistant"
                className="rounded-control inline-flex min-h-11 items-center justify-center gap-2 border border-white/25 px-4 font-medium text-white hover:bg-white/10"
              >
                <MessageSquareText
                  className="size-4"
                  strokeWidth={1.5}
                  aria-hidden="true"
                />
                {t("askTitle")}
              </Link>
            </div>
          </div>
          <div className="space-y-3 lg:self-start">
            <PracticeSnapshot />
          </div>
        </div>
      </section>

      <div className="space-y-10 px-6 py-8">
        <div
          className={`grid gap-8 ${obligations.length > 0 ? "lg:grid-cols-[minmax(0,1fr)_340px]" : ""}`}
        >
          <section aria-labelledby="recent-title" className="min-w-0">
            <div className="flex items-end justify-between gap-4">
              <h2 id="recent-title" className="text-xl font-semibold">
                {t("recentTitle")}
              </h2>
              <Link
                href="/matters"
                className="text-forest inline-flex items-center gap-1 text-sm font-medium hover:underline"
              >
                {t("viewAll")}
                <ArrowRight
                  className="size-4"
                  strokeWidth={1.5}
                  aria-hidden="true"
                />
              </Link>
            </div>
            <div className="rounded-card border-border bg-surface mt-4 overflow-hidden border">
              <RecentMatters />
            </div>
          </section>
          {obligations.length > 0 && (
            <section aria-labelledby="obligations-title">
              <h2 id="obligations-title" className="text-xl font-semibold">
                {t("obligationsTitle")}
              </h2>
              <ol className="rounded-card border-border bg-surface divide-border mt-4 divide-y overflow-hidden border">
                {obligations.map((obligation) => (
                  <li
                    key={obligation.id}
                    className="flex min-h-16 items-center gap-3 px-4"
                  >
                    <span className="bg-gold-soft text-gold-strong grid size-9 shrink-0 place-items-center rounded-lg">
                      <CalendarClock
                        className="size-4"
                        strokeWidth={1.5}
                        aria-hidden="true"
                      />
                    </span>
                    <span className="min-w-0 flex-1">
                      <span className="block text-sm font-medium">
                        {to(
                          obligation.labelKey.split(".").at(-1) as
                            | "monthlyList"
                            | "licenseRenewal"
                            | "lawyerReview",
                        )}
                      </span>
                      <span className="text-muted-ink block text-xs tabular-nums">
                        {t("due", {
                          date: format.dateTime(
                            new Date(`${obligation.dueDate}T00:00:00Z`),
                            {
                              day: "numeric",
                              month: "short",
                              year: "numeric",
                            },
                          ),
                        })}
                      </span>
                    </span>
                  </li>
                ))}
              </ol>
            </section>
          )}
        </div>

        <CommonWorkflows />
      </div>
    </AppShell>
  );
}
