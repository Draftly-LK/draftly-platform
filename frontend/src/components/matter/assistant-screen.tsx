"use client";

import {
  AlertTriangle,
  Check,
  ChevronRight,
  FileCheck2,
  FileText,
  ListChecks,
  LoaderCircle,
  MessageCircleQuestion,
  PanelRight,
  Plus,
  RotateCcw,
  Send,
  ShieldCheck,
  Sparkles,
  X,
} from "lucide-react";
import { useTranslations } from "next-intl";
import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";
import { AppShell } from "@/components/shell/app-shell";
import { Button } from "@/components/ui/button";
import { listIssues } from "@/lib/api/checks";
import { getDocumentInbox } from "@/lib/api/documents";
import { listForms } from "@/lib/api/drafts";
import { listMatterFacts } from "@/lib/api/facts";
import {
  confirmAgentAction,
  getAgentJob,
  isTerminalJobState,
  listAgentMessages,
  newIdempotencyKey,
  rejectAgentAction,
  sendAgentMessage,
  startAgentConversation,
  streamAgentJobEvents,
  type ApiAgentCitation,
  type ApiAgentJob,
  type ApiAgentMessage,
} from "@/lib/api/agent";
import { ApiError, apiErrorMessage } from "@/lib/api/client";
import { getChecklist, getMatter } from "@/lib/api/matters";
import { useTokenProvider } from "@/lib/api/use-token-provider";

const PAGE_SIZE = 20;
const POLL_INTERVAL_MS = 1200;
const MAX_POLLS = 40;
type Phase = "idle" | "sending" | "running" | "error";
interface PendingSend {
  content: string;
  idempotencyKey: string;
}
interface MatterContext {
  reference: string;
  state: string;
  documents: number | null;
  documentsPending: number | null;
  verifiedFacts: number | null;
  totalFacts: number | null;
  blockers: number | null;
  issues: number | null;
  drafts: number | null;
}

export function MatterAssistantScreen({ matterId }: { matterId: string }) {
  const t = useTranslations("matterAssistant");
  const getToken = useTokenProvider();
  const [messages, setMessages] = useState<ApiAgentMessage[]>([]);
  const [nextCursor, setNextCursor] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [phase, setPhase] = useState<Phase>("idle");
  const [job, setJob] = useState<ApiAgentJob | null>(null);
  const [draft, setDraft] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [actionBusy, setActionBusy] = useState<string | null>(null);
  const [context, setContext] = useState<MatterContext | null>(null);
  const [selectedCitation, setSelectedCitation] =
    useState<ApiAgentCitation | null>(null);
  const [contextOpen, setContextOpen] = useState(false);
  const pendingSend = useRef<PendingSend | null>(null);
  const endRef = useRef<HTMLDivElement | null>(null);
  const preserveScrollHeight = useRef<number | null>(null);

  const loadPage = useCallback(
    async (cursor?: string) => {
      if (cursor && typeof document !== "undefined") {
        preserveScrollHeight.current = document.documentElement.scrollHeight;
      }
      const page = await listAgentMessages(getToken, matterId, {
        limit: PAGE_SIZE,
        cursor,
      });
      const chronological = [...page.items].reverse();
      setMessages((previous) =>
        cursor ? [...chronological, ...previous] : chronological,
      );
      setNextCursor(page.page.hasMore ? page.page.nextCursor : null);
      requestAnimationFrame(() => {
        if (cursor && preserveScrollHeight.current !== null) {
          const addedHeight =
            document.documentElement.scrollHeight -
            preserveScrollHeight.current;
          window.scrollBy({ top: addedHeight });
          preserveScrollHeight.current = null;
        } else {
          endRef.current?.scrollIntoView({ block: "end" });
        }
      });
    },
    [getToken, matterId],
  );

  const loadContext = useCallback(async () => {
    const matter = await getMatter(getToken, matterId);
    const [inbox, facts, checklist, issues, forms] = await Promise.all([
      getDocumentInbox(getToken, matterId).catch(() => null),
      listMatterFacts(getToken, matterId).catch(() => null),
      getChecklist(getToken, matterId).catch(() => null),
      listIssues(getToken, matterId).catch(() => null),
      listForms(getToken, matterId).catch(() => null),
    ]);
    const visibleFacts =
      facts?.items.filter((fact) => fact.status !== "SUPERSEDED") ?? null;
    setContext({
      reference: matter.reference,
      state: matter.state,
      documents: inbox?.sourceFiles.length ?? null,
      documentsPending: inbox?.unprocessedSourceFileIds.length ?? null,
      verifiedFacts:
        visibleFacts?.filter((fact) =>
          ["LAWYER_CONFIRMED", "LOCKED_FOR_FORM"].includes(fact.status),
        ).length ?? null,
      totalFacts: visibleFacts?.length ?? null,
      blockers: checklist?.blockingRequirementIds.length ?? null,
      issues: issues?.items.length ?? null,
      drafts: forms?.items.length ?? null,
    });
  }, [getToken, matterId]);

  useEffect(() => {
    let active = true;
    setLoading(true);
    Promise.all([loadPage(), loadContext()])
      .catch((cause: unknown) => {
        if (active) setError(describe(cause, t));
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [loadContext, loadPage, t]);

  useEffect(() => {
    if (!loading) endRef.current?.scrollIntoView({ block: "end" });
  }, [loading]);

  useEffect(() => {
    if (!contextOpen) return;
    const closeOnEscape = (event: KeyboardEvent) => {
      if (event.key === "Escape") setContextOpen(false);
    };
    window.addEventListener("keydown", closeOnEscape);
    return () => window.removeEventListener("keydown", closeOnEscape);
  }, [contextOpen]);

  const watchJob = useCallback(
    async (jobId: string) => {
      const streamed = await streamAgentJobEvents(getToken, jobId, () => {});
      for (
        let attempt = 0;
        attempt < (streamed ? 1 : MAX_POLLS);
        attempt += 1
      ) {
        const current = await getAgentJob(getToken, jobId);
        setJob(current);
        if (isTerminalJobState(current.state)) return current;
        await sleep(POLL_INTERVAL_MS);
      }
      return null;
    },
    [getToken],
  );

  const runSend = useCallback(
    async (send: PendingSend) => {
      setPhase("sending");
      setError(null);
      try {
        const started = await sendAgentMessage(
          getToken,
          matterId,
          send.content,
          send.idempotencyKey,
        );
        setPhase("running");
        setJob(started);
        await loadPage();
        const finished = await watchJob(started.jobId);
        await loadPage();
        await loadContext();
        if (finished && finished.state !== "succeeded") {
          setError(t("turnFailed"));
          setPhase("error");
          return;
        }
        pendingSend.current = null;
        setPhase("idle");
      } catch (cause: unknown) {
        setError(describe(cause, t));
        setPhase("error");
      }
    },
    [getToken, loadContext, loadPage, matterId, t, watchJob],
  );

  const busy = phase === "sending" || phase === "running";
  const onSubmit = useCallback(() => {
    const content = draft.trim();
    if (!content || busy) return;
    const send = { content, idempotencyKey: newIdempotencyKey() };
    pendingSend.current = send;
    setDraft("");
    void runSend(send);
  }, [busy, draft, runSend]);

  const startFresh = useCallback(async () => {
    if (busy || !window.confirm(t("newConversationConfirm"))) return;
    setError(null);
    try {
      await startAgentConversation(getToken, matterId);
      setMessages([]);
      setNextCursor(null);
      setSelectedCitation(null);
      setDraft("");
    } catch (cause: unknown) {
      setError(describe(cause, t));
    }
  }, [busy, getToken, matterId, t]);

  const decide = useCallback(
    async (actionId: string, confirm: boolean) => {
      setActionBusy(actionId);
      setError(null);
      try {
        if (confirm) await confirmAgentAction(getToken, matterId, actionId);
        else await rejectAgentAction(getToken, matterId, actionId);
        await loadPage();
        await loadContext();
      } catch (cause: unknown) {
        setError(describe(cause, t));
      } finally {
        setActionBusy(null);
      }
    },
    [getToken, loadContext, loadPage, matterId, t],
  );

  const selectCitation = (citation: ApiAgentCitation) => {
    setSelectedCitation(citation);
    setContextOpen(true);
  };

  const contextPanel = (
    <ContextPanel
      context={context}
      matterId={matterId}
      selectedCitation={selectedCitation}
      onClearCitation={() => setSelectedCitation(null)}
      t={t}
    />
  );

  return (
    <AppShell matterId={matterId}>
      <div aria-live="polite" className="sr-only">
        {busy ? t("working") : ""}
      </div>
      <div className="grid min-h-[calc(100vh-260px)] xl:grid-cols-[minmax(0,1fr)_360px]">
        <main className="flex min-w-0 flex-col">
          <header className="border-border bg-surface flex min-h-16 items-center gap-3 border-b px-4 sm:px-6">
            <div className="min-w-0 flex-1">
              <h2 className="font-heading text-xl font-semibold">
                {t("title")}
              </h2>
              <p className="text-muted-ink truncate text-sm">
                {t("workspaceSubtitle")}
              </p>
            </div>
            <Button
              type="button"
              variant="secondary"
              className="xl:hidden"
              onClick={() => setContextOpen(true)}
            >
              <PanelRight className="size-4" strokeWidth={1.5} />
              {t("caseContext")}
            </Button>
            <Button
              type="button"
              variant="secondary"
              disabled={busy}
              onClick={() => void startFresh()}
            >
              <Plus className="size-4" strokeWidth={1.5} />
              {t("newConversation")}
            </Button>
          </header>

          <div className="mx-auto flex w-full max-w-4xl flex-1 flex-col px-4 sm:px-6">
            <section aria-label={t("thread")} className="flex-1 py-5">
              {nextCursor && (
                <div className="mb-5 text-center">
                  <Button
                    type="button"
                    variant="secondary"
                    onClick={() => void loadPage(nextCursor)}
                  >
                    {t("loadOlder")}
                  </Button>
                </div>
              )}
              {loading && (
                <p className="text-muted-ink flex items-center justify-center gap-2 py-16 text-sm">
                  <LoaderCircle className="size-4 animate-spin" />
                  {t("loading")}
                </p>
              )}
              {!loading && messages.length === 0 && (
                <EmptyThread onSelect={setDraft} t={t} />
              )}
              <div className="space-y-6">
                {messages.map((message) => (
                  <div key={message.id}>
                    <MessageRow
                      message={message}
                      onCitation={selectCitation}
                      t={t}
                    />
                    {message.pendingActionId && (
                      <ProposalCard
                        busy={actionBusy === message.pendingActionId}
                        onConfirm={() => decide(message.pendingActionId!, true)}
                        onReject={() => decide(message.pendingActionId!, false)}
                        t={t}
                      />
                    )}
                  </div>
                ))}
              </div>
              {busy && (
                <div
                  className="text-muted-ink mt-6 flex items-center gap-3 text-sm"
                  role="status"
                >
                  <div className="bg-selected-bg text-forest grid size-9 place-items-center rounded">
                    <LoaderCircle className="size-5 animate-spin" />
                  </div>
                  {job ? t("working") : t("sending")}
                </div>
              )}
              <div ref={endRef} />
            </section>
            {error && (
              <div
                role="alert"
                className="border-amber bg-amber-bg text-amber-text mb-3 flex items-start gap-3 rounded-card border p-3 text-sm"
              >
                <AlertTriangle className="size-5 shrink-0" />
                <span className="flex-1">{error}</span>
                {pendingSend.current && (
                  <Button
                    type="button"
                    variant="secondary"
                    onClick={() => {
                      const send = pendingSend.current;
                      if (send) void runSend(send);
                    }}
                  >
                    <RotateCcw className="size-4" />
                    {t("retry")}
                  </Button>
                )}
              </div>
            )}
            <Composer
              busy={busy}
              draft={draft}
              onChange={setDraft}
              onSubmit={onSubmit}
              t={t}
            />
          </div>
        </main>
        <aside className="border-border bg-surface hidden border-l xl:block">
          {contextPanel}
        </aside>
      </div>
      {contextOpen && (
        <div className="bg-scrim fixed inset-0 z-50 xl:hidden">
          <div
            role="dialog"
            aria-modal="true"
            aria-label={t("caseContext")}
            className="bg-surface ml-auto h-full w-full max-w-md overflow-y-auto"
          >
            <div className="border-border flex items-center border-b px-4 py-3">
              <h2 className="font-heading flex-1 text-xl font-semibold">
                {t("caseContext")}
              </h2>
              <Button
                type="button"
                variant="secondary"
                onClick={() => setContextOpen(false)}
              >
                <X className="size-4" />
                {t("close")}
              </Button>
            </div>
            {contextPanel}
          </div>
        </div>
      )}
    </AppShell>
  );
}

function MessageRow({
  message,
  onCitation,
  t,
}: {
  message: ApiAgentMessage;
  onCitation: (citation: ApiAgentCitation) => void;
  t: ReturnType<typeof useTranslations>;
}) {
  const assistant = message.role === "assistant";
  return (
    <article
      className={assistant ? "max-w-3xl" : "ml-auto max-w-[85%]"}
      data-role={message.role}
    >
      <div
        className={`flex items-start gap-3 ${assistant ? "" : "flex-row-reverse"}`}
      >
        <div className="bg-selected-bg text-forest grid size-9 shrink-0 place-items-center rounded">
          {assistant ? (
            <Sparkles className="size-5" />
          ) : (
            <MessageCircleQuestion className="size-5" />
          )}
        </div>
        <div
          className={
            assistant
              ? "min-w-0 flex-1"
              : "border-border-strong bg-surface min-w-0 rounded border px-4 py-3"
          }
        >
          <div
            className={`text-muted-ink flex gap-2 text-xs font-semibold ${assistant ? "" : "justify-end"}`}
          >
            <span>{assistant ? t("roleAssistant") : t("roleYou")}</span>
            <time
              className="font-normal normal-case"
              dateTime={message.createdAt}
            >
              {new Date(message.createdAt).toLocaleTimeString([], {
                hour: "2-digit",
                minute: "2-digit",
              })}
            </time>
          </div>
          <p className="mt-1 whitespace-pre-wrap leading-7">
            {renderCitedText(message.content, message.citations, onCitation)}
          </p>
          {assistant && message.citations.length > 0 && (
            <div
              className="mt-3 flex flex-wrap gap-2"
              aria-label={t("evidenceUsed")}
            >
              {message.citations.map((citation, index) => (
                <button
                  key={`${message.id}-${citation.sourceId}`}
                  type="button"
                  className="border-border-strong bg-surface text-forest focus-visible:outline-ring rounded-control border px-2 py-1 text-xs focus-visible:outline-2"
                  onClick={() => onCitation(citation)}
                >
                  [{index + 1}] {citation.label}
                </button>
              ))}
            </div>
          )}
          {assistant && (
            <p className="text-muted-ink mt-3 text-xs">
              {t("unverifiedNotice")}
            </p>
          )}
        </div>
      </div>
    </article>
  );
}

function renderCitedText(
  content: string,
  citations: ApiAgentCitation[],
  onCitation: (citation: ApiAgentCitation) => void,
) {
  return content.split(/(\[\d+\])/g).map((part, index) => {
    const match = /^\[(\d+)\]$/.exec(part);
    if (!match) return part;
    const citation = citations[Number(match[1]) - 1];
    if (!citation) return part;
    return (
      <button
        key={`${citation.sourceId}-${index}`}
        type="button"
        className="text-forest focus-visible:outline-ring mx-0.5 font-semibold hover:underline focus-visible:outline-2"
        aria-label={`${citation.label}, ${citation.verificationStatus}`}
        onClick={() => onCitation(citation)}
      >
        {part}
      </button>
    );
  });
}

function Composer({
  busy,
  draft,
  onChange,
  onSubmit,
  t,
}: {
  busy: boolean;
  draft: string;
  onChange: (value: string) => void;
  onSubmit: () => void;
  t: ReturnType<typeof useTranslations>;
}) {
  return (
    <form
      className="border-border-control bg-surface shadow-popover sticky bottom-3 mb-3 rounded border p-3 focus-within:border-forest focus-within:ring-4 focus-within:ring-border-active"
      onSubmit={(event) => {
        event.preventDefault();
        onSubmit();
      }}
    >
      <label className="sr-only" htmlFor="matter-assistant-composer">
        {t("composerLabel")}
      </label>
      <textarea
        id="matter-assistant-composer"
        className="min-h-20 w-full resize-y border-0 bg-transparent p-2 outline-none focus-visible:outline-none"
        placeholder={t("composerPlaceholder")}
        value={draft}
        disabled={busy}
        onChange={(event) => onChange(event.target.value)}
        onKeyDown={(event) => {
          if (event.key === "Enter" && !event.shiftKey) {
            event.preventDefault();
            onSubmit();
          }
        }}
      />
      <div className="border-border flex items-center gap-3 border-t pt-3">
        <p className="text-muted-ink text-xs">{t("composerNotice")}</p>
        <Button
          type="submit"
          className="ml-auto"
          variant="primary"
          disabled={busy || !draft.trim()}
        >
          {t("send")}
          <Send className="size-4" />
        </Button>
      </div>
    </form>
  );
}

function EmptyThread({
  onSelect,
  t,
}: {
  onSelect: (question: string) => void;
  t: ReturnType<typeof useTranslations>;
}) {
  const suggestions = [
    t("suggestOverview"),
    t("suggestMissing"),
    t("suggestNext"),
  ];
  return (
    <div className="mx-auto max-w-xl py-12 text-center">
      <div className="bg-selected-bg text-forest mx-auto grid size-12 place-items-center rounded">
        <Sparkles className="size-6" />
      </div>
      <h3 className="font-heading mt-4 text-xl font-semibold">
        {t("emptyTitle")}
      </h3>
      <p className="text-muted-ink mt-2 text-sm leading-6">{t("emptyBody")}</p>
      <div className="mt-5 flex flex-wrap justify-center gap-2">
        {suggestions.map((suggestion) => (
          <button
            key={suggestion}
            type="button"
            className="border-border-strong bg-surface hover:bg-hover-bg rounded-control border px-3 py-2 text-sm"
            onClick={() => onSelect(suggestion)}
          >
            {suggestion}
          </button>
        ))}
      </div>
    </div>
  );
}

function ContextPanel({
  context,
  matterId,
  selectedCitation,
  onClearCitation,
  t,
}: {
  context: MatterContext | null;
  matterId: string;
  selectedCitation: ApiAgentCitation | null;
  onClearCitation: () => void;
  t: ReturnType<typeof useTranslations>;
}) {
  const tNav = useTranslations("matterNav");
  if (selectedCitation)
    return (
      <div className="p-5">
        <button
          type="button"
          className="text-forest text-sm hover:underline"
          onClick={onClearCitation}
        >
          {t("backToContext")}
        </button>
        <div className="border-border-strong mt-4 rounded border p-4">
          <div className="text-muted-ink text-xs font-semibold">
            {t("evidence")}
          </div>
          <h3 className="mt-1 font-semibold">{selectedCitation.label}</h3>
          <p className="text-muted-ink mt-2 break-all text-sm">
            {selectedCitation.sourceId}
          </p>
          <p className="mt-3 flex items-center gap-2 text-sm">
            {selectedCitation.verificationStatus === "verified" ? (
              <ShieldCheck className="text-teal size-4" />
            ) : (
              <AlertTriangle className="text-amber-text size-4" />
            )}
            {t(`verification.${selectedCitation.verificationStatus}`)}
          </p>
          <Link
            href={citationHref(matterId, selectedCitation)}
            className="text-forest mt-4 inline-flex items-center gap-1 text-sm font-medium hover:underline"
          >
            {t("openSource")}
            <ChevronRight className="size-4" />
          </Link>
        </div>
      </div>
    );
  const metrics = [
    {
      icon: FileText,
      label: t("contextDocuments"),
      value: context
        ? formatPair(context.documents, context.documentsPending, t("pending"))
        : "…",
      href: `/matters/${matterId}/documents`,
    },
    {
      icon: ShieldCheck,
      label: t("contextFacts"),
      value: context
        ? formatRatio(context.verifiedFacts, context.totalFacts)
        : "…",
      href: `/matters/${matterId}/facts`,
    },
    {
      icon: ListChecks,
      label: t("contextChecks"),
      value: context
        ? formatPair(context.blockers, context.issues, t("issues"))
        : "…",
      href: `/matters/${matterId}/checks`,
    },
    {
      icon: FileCheck2,
      label: t("contextDrafts"),
      value: context ? valueOrUnavailable(context.drafts) : "…",
      href: `/matters/${matterId}/drafts`,
    },
  ];
  return (
    <div>
      <div className="border-border border-b p-5">
        <div className="text-muted-ink text-xs font-semibold">
          {t("caseContext")}
        </div>
        <h2 className="font-heading mt-1 text-xl font-semibold">
          {context?.reference ?? t("loadingContext")}
        </h2>
        {context && (
          <p className="text-muted-ink mt-1 text-sm">
            {t("matterState", { state: tNav(`stateLabel.${context.state}`) })}
          </p>
        )}
      </div>
      <div className="divide-border divide-y">
        {metrics.map(({ icon: Icon, label, value, href }) => (
          <Link
            key={label}
            href={href}
            className="hover:bg-hover-bg flex min-h-20 items-center gap-3 px-5 py-4"
          >
            <Icon className="text-forest size-5 shrink-0" />
            <div className="min-w-0 flex-1">
              <div className="text-muted-ink text-xs font-semibold">
                {label}
              </div>
              <div className="mt-1 text-sm">{value}</div>
            </div>
            <ChevronRight className="text-muted-ink size-4" />
          </Link>
        ))}
      </div>
      <p className="text-muted-ink border-border border-t p-5 text-xs leading-5">
        {t("contextNotice")}
      </p>
    </div>
  );
}

function ProposalCard({
  busy,
  onConfirm,
  onReject,
  t,
}: {
  busy: boolean;
  onConfirm: () => void;
  onReject: () => void;
  t: ReturnType<typeof useTranslations>;
}) {
  return (
    <div
      className="border-amber bg-amber-bg ml-12 mt-3 rounded-card border p-4"
      data-testid="proposal-card"
    >
      <p className="text-sm font-semibold">{t("proposalTitle")}</p>
      <p className="text-amber-text mt-1 flex items-center gap-2 text-xs">
        <AlertTriangle className="size-4" />
        {t("proposalNothingChanged")}
      </p>
      <div className="mt-3 flex gap-2">
        <Button
          type="button"
          variant="primary"
          disabled={busy}
          onClick={onConfirm}
        >
          <Check className="size-4" />
          {t("confirm")}
        </Button>
        <Button
          type="button"
          variant="secondary"
          disabled={busy}
          onClick={onReject}
        >
          <X className="size-4" />
          {t("reject")}
        </Button>
      </div>
    </div>
  );
}

function citationHref(matterId: string, citation: ApiAgentCitation): string {
  const suffix = {
    matter: "",
    document: "/documents",
    fact: "/facts",
    check: "/checks",
    draft: "/drafts",
    party: "",
    record: "",
  }[citation.sourceType];
  const query = new URLSearchParams({ source: citation.sourceId });
  if (citation.locator) query.set("locator", citation.locator);
  return `/matters/${matterId}${suffix}?${query.toString()}`;
}
function valueOrUnavailable(value: number | null) {
  return value === null ? "—" : String(value);
}
function formatRatio(value: number | null, total: number | null) {
  return value === null || total === null ? "—" : `${value} / ${total}`;
}
function formatPair(
  primary: number | null,
  secondary: number | null,
  label: string,
) {
  return primary === null || secondary === null
    ? "—"
    : `${primary} · ${secondary} ${label}`;
}
function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}
function describe(
  cause: unknown,
  t: ReturnType<typeof useTranslations>,
): string {
  if (cause instanceof ApiError) {
    if (cause.code === "pending_action_stale") return t("errorStale");
    if (cause.code === "capability_denied") return t("errorCapability");
    if (cause.code === "matter_agent_disabled") return t("errorDisabled");
    if (cause.code === "agent_model_unavailable") return t("errorProvider");
    return apiErrorMessage(cause, t("errorUnknown"));
  }
  return t("errorUnknown");
}
