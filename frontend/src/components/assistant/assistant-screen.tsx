"use client";

import {
  BookMarked,
  FileCheck2,
  Library,
  MessageSquareText,
  Mic,
  PanelRightClose,
  PanelRightOpen,
  PlusCircle,
  Send,
  ShieldCheck,
} from "lucide-react";
import { useLocale, useTranslations } from "next-intl";
import { useState } from "react";
import { answers } from "@/lib/mocks";
import {
  authorityTypeLabels,
  authorityWeightLabels,
  courtLevelLabels,
} from "@/lib/i18n/labels";
import { useDemoStore } from "@/lib/store";
import type { Citation } from "@/types";
import { AppShell } from "@/components/shell/app-shell";
import { PageHeader } from "@/components/shell/page-header";
import { Button } from "@/components/ui/button";
import { IconButton } from "@/components/ui/icon-button";

export function AssistantScreen() {
  const t = useTranslations("assistant");
  const locale = useLocale() === "si" ? "si" : "en";
  const recordAction = useDemoStore((state) => state.recordAssistantAction);
  const grounded = answers.find((answer) => answer.kind === "grounded");
  const insufficient = answers.find(
    (answer) => answer.kind === "insufficient-authority",
  );
  const firstCitation =
    grounded?.kind === "grounded"
      ? grounded.claims[0]?.citations[0]
      : undefined;
  const [citation, setCitation] = useState<Citation | undefined>(firstCitation);
  const [evidenceOpen, setEvidenceOpen] = useState(true);
  const [question, setQuestion] = useState("");
  const [announcement, setAnnouncement] = useState("");
  const action = (name: string) => {
    recordAction(grounded?.id ?? "answer-grounded", name);
    setAnnouncement(t("actionRecorded"));
  };
  const submit = () => {
    if (!question.trim()) return;
    recordAction("answer-grounded", "question-asked");
    setQuestion("");
    setAnnouncement(t("questionRecorded"));
  };
  if (
    !grounded ||
    grounded.kind !== "grounded" ||
    !insufficient ||
    insufficient.kind !== "insufficient-authority"
  )
    return null;
  return (
    <AppShell>
      <PageHeader title={t("title")} description={t("description")} />
      <div aria-live="polite" className="sr-only">
        {announcement}
      </div>
      <div
        className={`grid min-h-[calc(100vh-105px)] ${evidenceOpen ? "min-[1280px]:grid-cols-[minmax(0,1fr)_380px]" : ""}`}
      >
        <main className="min-w-0 p-6">
          <section aria-labelledby="scope-title">
            <h2 id="scope-title" className="text-sm font-semibold">
              {t("scope")}
            </h2>
            <div
              className="mt-2 flex flex-wrap gap-2"
              role="group"
              aria-label={t("scope")}
            >
              <ScopeChip
                active
                icon={<MessageSquareText />}
                label={t("matterScope")}
              />
              <ScopeChip icon={<FileCheck2 />} label={t("stepScope")} />
              <ScopeChip icon={<BookMarked />} label={t("documentScope")} />
              <ScopeChip icon={<Library />} label={t("libraryScope")} />
            </div>
          </section>
          <form
            className="border-border-strong bg-surface shadow-popover mt-5 rounded border p-3"
            onSubmit={(event) => {
              event.preventDefault();
              submit();
            }}
          >
            <label className="sr-only" htmlFor="assistant-question">
              {t("composerLabel")}
            </label>
            <textarea
              id="assistant-question"
              className="min-h-24 w-full resize-y border-0 bg-transparent p-2 outline-none"
              placeholder={t("composerPlaceholder")}
              value={question}
              onChange={(event) => setQuestion(event.target.value)}
            />
            <div className="border-border flex items-center gap-2 border-t pt-3">
              <IconButton type="button" label={t("dictate")}>
                <Mic className="size-5" strokeWidth={1.5} />
              </IconButton>
              <Button
                type="submit"
                className="ml-auto"
                variant="primary"
                disabled={!question.trim()}
              >
                {t("send")}
                <Send className="size-4" strokeWidth={1.5} />
              </Button>
            </div>
          </form>
          <section className="border-border-strong bg-surface mt-6 rounded border">
            <header className="border-border flex items-center gap-3 border-b px-5 py-4">
              <div className="bg-soft-green text-forest grid size-9 place-items-center rounded">
                <ShieldCheck className="size-5" strokeWidth={1.5} />
              </div>
              <div className="min-w-0 flex-1">
                <h2 className="text-2xl font-semibold">{t("answer")}</h2>
                <p className="text-muted-ink truncate text-sm">
                  {grounded.question}
                </p>
              </div>
              <IconButton
                label={evidenceOpen ? t("hideEvidence") : t("showEvidence")}
                onClick={() => setEvidenceOpen((value) => !value)}
              >
                {evidenceOpen ? (
                  <PanelRightClose className="size-5" strokeWidth={1.5} />
                ) : (
                  <PanelRightOpen className="size-5" strokeWidth={1.5} />
                )}
              </IconButton>
            </header>
            <div className="divide-border divide-y">
              {grounded.claims.map((claim, claimIndex) => (
                <article key={claim.id} className="p-5">
                  <div className="text-muted-ink text-xs font-semibold uppercase">
                    {t("questionPart", { number: claimIndex + 1 })}
                  </div>
                  <p className="mt-2 text-base leading-7">{claim.text}</p>
                  <div className="mt-4 flex flex-wrap gap-2">
                    {claim.citations.map((item, index) => (
                      <button
                        key={item.id}
                        className={`inline-flex min-h-9 items-center gap-2 rounded border px-3 text-sm ${citation?.id === item.id ? "border-teal bg-teal-bg text-teal" : "border-border-strong hover:bg-hover-bg"}`}
                        onClick={() => {
                          setCitation(item);
                          setEvidenceOpen(true);
                        }}
                      >
                        <BookMarked className="size-4" strokeWidth={1.5} />
                        {item.authority.reference} ·{" "}
                        {t("citation", { number: index + 1 })}
                      </button>
                    ))}
                  </div>
                  <div className="mt-4 flex flex-wrap gap-2">
                    <Button onClick={() => action("added-to-matter")}>
                      {t("addToMatter")}
                    </Button>
                    <Button onClick={() => action("saved-to-library")}>
                      {t("saveToLibrary")}
                    </Button>
                    <Button onClick={() => action("check-created")}>
                      <PlusCircle className="size-4" />
                      {t("createCheck")}
                    </Button>
                  </div>
                </article>
              ))}
            </div>
            <footer className="border-border bg-canvas text-muted-ink border-t px-5 py-3 text-sm">
              <strong className="text-ink">{t("corpusLimits")}:</strong>{" "}
              {t("corpusLimit")}
            </footer>
          </section>
          <section className="border-red bg-red-bg mt-6 border-l-2 p-5">
            <div className="flex items-center gap-3">
              <ShieldCheck className="text-red size-6" strokeWidth={1.5} />
              <div>
                <h2 className="text-red text-xl font-semibold">
                  {t("insufficientTitle")}
                </h2>
                <p className="mt-1">{t("insufficientReason")}</p>
              </div>
            </div>
            <p className="mt-3 text-sm">{t("insufficientAction")}</p>
            <div className="mt-4 flex flex-wrap gap-2">
              <Button>{t("refine")}</Button>
              <Button onClick={() => action("authority-review-requested")}>
                {t("requestReview")}
              </Button>
            </div>
          </section>
        </main>
        {evidenceOpen && (
          <aside className="border-border bg-canvas hidden border-l p-5 min-[1280px]:block">
            <h2 className="text-2xl font-semibold">{t("evidence")}</h2>
            {citation ? (
              <>
                <div className="border-border-strong bg-surface mt-4 rounded border p-4">
                  <div className="text-teal text-xs font-semibold uppercase">
                    {t("exactText")}
                  </div>
                  <p className="font-heading mt-2 text-lg leading-7">
                    {citation.evidence.snippet}
                  </p>
                  <div className="text-muted-ink mt-3 text-sm">
                    {citation.evidence.documentId} · {t("page", { page: citation.evidence.page })}
                  </div>
                </div>
                <div className="border-border-strong bg-surface mt-4 rounded border p-4">
                  <div className="text-muted-ink text-xs font-semibold uppercase">
                    {t("authority")}
                  </div>
                  <div className="font-heading mt-2 text-xl font-semibold">
                    {citation.authority.title}
                  </div>
                  <div className="text-muted-ink mt-1 text-sm">
                    {citation.authority.reference}
                  </div>
                  <div className="mt-3 flex flex-wrap gap-2">
                    <AuthorityBadge
                      label={
                        authorityTypeLabels[citation.authority.type][locale]
                      }
                    />
                    <AuthorityBadge
                      label={
                        courtLevelLabels[citation.authority.courtLevel][locale]
                      }
                    />
                    <AuthorityBadge
                      label={
                        authorityWeightLabels[citation.authority.weight][locale]
                      }
                    />
                    <AuthorityBadge
                      label={
                        citation.authority.verified
                          ? t("verifiedAuthority")
                          : t("unverifiedAuthority")
                      }
                      verified={citation.authority.verified}
                    />
                  </div>
                </div>
              </>
            ) : (
              <p className="text-muted-ink mt-4">{t("noCitation")}</p>
            )}
          </aside>
        )}
      </div>
    </AppShell>
  );
}

function ScopeChip({
  icon,
  label,
  active = false,
}: {
  icon: React.ReactNode;
  label: string;
  active?: boolean;
}) {
  return (
    <button
      aria-pressed={active}
      className={`inline-flex min-h-10 items-center gap-2 rounded-full border px-3 text-sm [&_svg]:size-4 [&_svg]:stroke-[1.5] ${active ? "border-forest bg-soft-green text-forest" : "border-border-strong bg-surface hover:bg-hover-bg"}`}
    >
      {icon}
      {label}
    </button>
  );
}

function AuthorityBadge({
  label,
  verified = false,
}: {
  label: string;
  verified?: boolean;
}) {
  return (
    <span
      className={`inline-flex min-h-7 items-center gap-1 rounded-full border px-2 py-1 text-xs font-semibold ${verified ? "border-forest bg-soft-green text-forest" : "border-border-strong bg-canvas"}`}
    >
      <ShieldCheck className="size-3.5" strokeWidth={1.5} />
      {label}
    </span>
  );
}
