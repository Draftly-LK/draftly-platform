import {
  ArrowRight,
  CalendarClock,
  FilePlus2,
  MessageSquareText,
  Workflow,
} from "lucide-react";
import { getFormatter, getTranslations } from "next-intl/server";
import Link from "next/link";
import { demoOnly, obligations as obligationFixtures } from "@/lib/mocks";
import { CommonWorkflows } from "@/components/home/common-workflows";
import { PracticeSnapshot } from "@/components/home/practice-snapshot";
import { RecentMatters } from "@/components/home/recent-matters";
import { AppShell } from "@/components/shell/app-shell";
import { LocaleToggle } from "@/components/shell/locale-toggle";

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
    {
      href: "/workflows",
      title: t("workflowTitle"),
      body: t("workflowBody"),
      icon: Workflow,
    },
  ];
  return (
    <AppShell>
      <section
        aria-labelledby="home-title"
        className="bg-navy-900 relative isolate overflow-hidden border-b-2 border-gold text-white"
      >
        <div className="grid items-end gap-8 px-6 pb-9 pt-8 lg:grid-cols-[minmax(0,1fr)_440px] lg:px-10">
          <div className="animate-rise-in">
            <div className="flex items-center justify-between gap-4">
              <p className="text-gold text-xs font-semibold uppercase tracking-[0.12em]">{t("eyebrow")}</p>
              <div className="lg:hidden">
                <LocaleToggle />
              </div>
            </div>
            <h1 id="home-title" className="font-display mt-3 text-[44px] font-semibold leading-[1.05] sm:text-[52px]">
              {t("title")}
            </h1>
            <p className="text-on-dark-muted mt-3 max-w-xl text-[17px]">{t("description")}</p>
            <div className="mt-7 flex flex-wrap gap-3">
              <Link
                href="/new"
                className="bg-gold text-navy-950 inline-flex min-h-11 items-center gap-2 rounded px-4 font-semibold hover:brightness-105"
              >
                <FilePlus2 className="size-4" strokeWidth={1.5} aria-hidden="true" />
                {t("createTitle")}
              </Link>
              <Link
                href="/assistant"
                className="inline-flex min-h-11 items-center gap-2 rounded border border-white/25 px-4 font-medium text-white hover:bg-white/10"
              >
                <MessageSquareText className="size-4" strokeWidth={1.5} aria-hidden="true" />
                {t("askTitle")}
              </Link>
            </div>
          </div>
          <div className="animate-rise-in space-y-3 [animation-delay:80ms]">
            <div className="hidden justify-end lg:flex">
              <LocaleToggle />
            </div>
            <PracticeSnapshot />
          </div>
        </div>
      </section>

      <div className="mx-auto max-w-[1200px] space-y-10 px-6 py-8 lg:px-10">
        <section aria-labelledby="command-title">
          <h2 id="command-title" className="text-xl font-semibold">
            {t("commandTitle")}
          </h2>
          <div className="mt-4 grid gap-4 md:grid-cols-3">
            {actions.map(({ href, title, body, icon: Icon }) => (
              <Link
                href={href}
                key={href}
                className="rounded-card border-border bg-surface shadow-card hover:border-border-strong hover:shadow-raised group flex min-h-28 items-start gap-4 border p-5 transition-shadow"
              >
                <span className="bg-selected-bg text-forest group-hover:bg-forest grid size-11 shrink-0 place-items-center rounded-lg transition-colors group-hover:text-white">
                  <Icon className="size-5" strokeWidth={1.5} />
                </span>
                <span className="min-w-0 flex-1">
                  <span className="block font-semibold">{title}</span>
                  <span className="text-muted-ink mt-1 block text-sm">{body}</span>
                </span>
                <ArrowRight
                  className="text-muted-ink group-hover:text-forest mt-1 size-4 shrink-0 transition-transform group-hover:translate-x-0.5"
                  strokeWidth={1.5}
                />
              </Link>
            ))}
          </div>
        </section>

        <div className={`grid gap-8 ${obligations.length > 0 ? "lg:grid-cols-[minmax(0,1fr)_340px]" : ""}`}>
          <section aria-labelledby="recent-title" className="min-w-0">
            <div className="flex items-end justify-between gap-4">
              <h2 id="recent-title" className="text-xl font-semibold">
                {t("recentTitle")}
              </h2>
              <Link href="/matters" className="text-teal inline-flex items-center gap-1 text-sm font-medium hover:underline">
                {t("viewAll")}
                <ArrowRight className="size-4" strokeWidth={1.5} aria-hidden="true" />
              </Link>
            </div>
            <div className="rounded-card border-border bg-surface shadow-card mt-4 overflow-hidden border">
              <RecentMatters />
            </div>
          </section>
          {obligations.length > 0 && (
            <section aria-labelledby="obligations-title">
              <h2 id="obligations-title" className="text-xl font-semibold">
                {t("obligationsTitle")}
              </h2>
              <ol className="rounded-card border-border bg-surface shadow-card divide-border mt-4 divide-y overflow-hidden border">
                {obligations.map((obligation) => (
                  <li key={obligation.id} className="flex min-h-16 items-center gap-3 px-4">
                    <span className="bg-gold-soft text-gold-strong grid size-9 shrink-0 place-items-center rounded-lg">
                      <CalendarClock className="size-4" strokeWidth={1.5} aria-hidden="true" />
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
                          date: format.dateTime(new Date(`${obligation.dueDate}T00:00:00Z`), {
                            day: "numeric",
                            month: "short",
                            year: "numeric",
                          }),
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
