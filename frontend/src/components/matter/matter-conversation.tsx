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
  PanelRightClose,
  PanelRightOpen,
  Plus,
  RotateCcw,
  ShieldCheck,
  Sparkles,
  X,
} from "lucide-react";
import type { DigitalReviewStatus } from "@/types/rta";
import { useTranslations } from "next-intl";
import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";
import {
  LegalResultContext,
  LegalAuthorityPanel,
  LegalTransactionSelector,
  type LegalSourceSelection,
} from "./legal-source-context";
import type { ApiResearchSelection } from "@/lib/api/agent";
import { ChatComposer } from "@/components/assistant/chat-composer";
import { getMe } from "@/lib/api/auth";
import {
  clearManualIntent,
  pendingOperationIntent,
  readPendingOperationIntent,
  type ManualIntent,
} from "@/lib/api/mutation-intent";
import { PageHeader } from "@/components/shell/page-header";
import { Button } from "@/components/ui/button";
import { IconButton } from "@/components/ui/icon-button";
import { cn } from "@/lib/utils";
import { listCompleteIssues } from "@/lib/api/checks";
import { SourceFilePreview } from "./source-file-preview";
import { getSourceFile, getCompleteDocumentInbox } from "@/lib/api/documents";
import { listForms } from "@/lib/api/drafts";
import { listMatterFacts } from "@/lib/api/facts";
import {
  confirmAgentAction,
  getAgentJob,
  getAgentSession,
  getAgentSendReceipt,
  getLatestAgentJob,
  getAgentAction,
  type ApiPendingAction,
  isTerminalJobState,
  listAgentMessages,
  rejectAgentAction,
  retryAgentJob,
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
// Cover the backend's 120-second turn budget, plus queueing margin.
const MAX_POLLS = 125;
type Phase = "idle" | "sending" | "running" | "error";
interface PendingSend {
  content: string;
  selection?: ApiResearchSelection | null;
  idempotencyKey: string;
  retryJobId?: string;
  watchJobId?: string;
  intent?: ManualIntent;
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

export function MatterConversation({
  matterId,
  embedded = false,
  onChanged,
}: {
  matterId: string;
  embedded?: boolean;
  onChanged?: () => void;
}) {
  const t = useTranslations("matterAssistant");
  const getToken = useTokenProvider();
  const [messages, setMessages] = useState<ApiAgentMessage[]>([]);
  const [nextCursor, setNextCursor] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [phase, setPhase] = useState<Phase>("idle");
  const [job, setJob] = useState<ApiAgentJob | null>(null);
  const [draft, setDraft] = useState("");
  const [legalSelection, setLegalSelection] =
    useState<ApiResearchSelection | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [actionBusy, setActionBusy] = useState<string | null>(null);
  const [context, setContext] = useState<MatterContext | null>(null);
  const [selectedCitation, setSelectedCitation] =
    useState<LegalSourceSelection | null>(null);
  const [contextOpen, setContextOpen] = useState(false);
  const [panelCollapsed, setPanelCollapsed] = usePanelCollapsed();
  const pendingSend = useRef<PendingSend | null>(null);
  const busyRef = useRef(false);
  const lifetime = useRef<AbortController | null>(null);
  const identity = useRef<{
    actorId: string;
    conversationId: string | null;
  } | null>(null);
  const [actions, setActions] = useState<Record<string, ApiPendingAction>>({});
  const dialogRef = useRef<HTMLDivElement | null>(null);
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
      if (lifetime.current?.signal.aborted) return;
      const actionIds = [
        ...new Set(
          page.items.flatMap((m) =>
            m.pendingActionId ? [m.pendingActionId] : [],
          ),
        ),
      ];
      const cards = await Promise.all(
        actionIds.map((id) =>
          getAgentAction(getToken, matterId, id).catch(() => null),
        ),
      );
      if (lifetime.current?.signal.aborted) return;
      setActions((previous) => ({
        ...previous,
        ...Object.fromEntries(
          cards.filter((card) => card !== null).map((card) => [card.id, card]),
        ),
      }));
      // A fresh policy projection must replace any previously opened passage.
      if (!cursor) setSelectedCitation(null);
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
        } else if (!embedded) {
          endRef.current?.scrollIntoView({ block: "end" });
        }
      });
    },
    [getToken, matterId, embedded],
  );

  const loadContext = useCallback(async () => {
    const matter = await getMatter(getToken, matterId);
    const [inbox, facts, checklist, issues, forms] = await Promise.all([
      getCompleteDocumentInbox(getToken, matterId).catch(() => null),
      listMatterFacts(getToken, matterId).catch(() => null),
      getChecklist(getToken, matterId).catch(() => null),
      listCompleteIssues(getToken, matterId).catch(() => null),
      listForms(getToken, matterId).catch(() => null),
    ]);
    const visibleFacts =
      facts && !facts.page?.hasMore
        ? facts.items.filter((fact) => fact.status !== "SUPERSEDED")
        : null;
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
      issues:
        issues && !issues.page?.hasMore
          ? issues.items.filter(
              (issue) =>
                !["RESOLVED", "ACCEPTED_RISK", "FALSE_POSITIVE"].includes(
                  issue.state,
                ),
            ).length
          : null,
      drafts: forms && !forms.page?.hasMore ? forms.items.length : null,
    });
  }, [getToken, matterId]);

  useEffect(() => {
    if (!contextOpen || window.matchMedia("(min-width: 1280px)").matches)
      return;
    const previous =
      document.activeElement instanceof HTMLElement
        ? document.activeElement
        : null;
    const panel = dialogRef.current;
    const focusable = () =>
      Array.from(
        panel?.querySelectorAll<HTMLElement>(
          'button:not([disabled]), a[href], input:not([disabled]), [tabindex="0"]',
        ) ?? [],
      );
    (focusable()[0] ?? panel)?.focus();
    const handleKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        event.preventDefault();
        setContextOpen(false);
      }
      if (event.key !== "Tab") return;
      const items = focusable();
      const first = items[0];
      const last = items.at(-1);
      if (!first || !last) {
        event.preventDefault();
        panel?.focus();
      } else if (
        event.shiftKey &&
        (document.activeElement === first || document.activeElement === panel)
      ) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    };
    window.addEventListener("keydown", handleKey);
    return () => {
      window.removeEventListener("keydown", handleKey);
      previous?.focus();
    };
  }, [contextOpen]);

  const watchJob = useCallback(
    async (jobId: string) => {
      const signal = lifetime.current?.signal;
      await streamAgentJobEvents(getToken, jobId, () => {}, signal);
      for (let attempt = 0; attempt < MAX_POLLS; attempt += 1) {
        if (signal?.aborted) return null;
        const current = await getAgentJob(getToken, jobId);
        if (signal?.aborted) return null;
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
      if (busyRef.current) return;
      busyRef.current = true;
      setPhase("sending");
      setError(null);
      try {
        if (send.retryJobId && !send.idempotencyKey) {
          const owner = identity.current;
          if (!owner) throw new Error("Conversation unavailable");
          send.intent = await pendingOperationIntent(
            owner.actorId,
            matterId,
            `agent-retry:${send.retryJobId}`,
            { jobId: send.retryJobId },
          );
          send.idempotencyKey = send.intent.key;
        }
        const started = send.watchJobId
          ? await getAgentJob(getToken, send.watchJobId)
          : send.retryJobId
            ? await retryAgentJob(
                getToken,
                matterId,
                send.retryJobId,
                send.idempotencyKey,
              )
            : await sendAgentMessage(
                getToken,
                matterId,
                send.content,
                send.idempotencyKey,
                send.selection,
              );
        if (send.intent) clearManualIntent(send.intent);
        if (lifetime.current?.signal.aborted) return;
        setPhase("running");
        setJob(started);
        pendingSend.current = { ...send, watchJobId: started.jobId };
        await loadPage();
        const finished = await watchJob(started.jobId);
        await loadPage();
        await loadContext();
        onChanged?.();
        if (lifetime.current?.signal.aborted) return;
        if (!finished) {
          // An unfinished status is not success. Checking again watches this
          // same accepted job and cannot append a duplicate user message.
          setError(t("working"));
          setPhase("error");
          return;
        }
        if (finished && finished.state !== "succeeded") {
          // A failed job is terminal. Replaying its original send key cannot
          // execute it again; retry its saved message as a distinct attempt.
          pendingSend.current = retryable(finished)
            ? {
                content: send.content,
                retryJobId: finished.jobId,
                idempotencyKey: "",
              }
            : null;
          setError(
            t(
              finished.toolCallCount > 0
                ? "turnFailedAfterTools"
                : "turnFailed",
            ),
          );
          setPhase("error");
          return;
        }
        pendingSend.current = null;
        setPhase("idle");
      } catch (cause: unknown) {
        if (
          cause instanceof ApiError &&
          cause.code === "agent_retry_unavailable"
        ) {
          pendingSend.current = null;
        }
        if (!lifetime.current?.signal.aborted) {
          setError(describe(cause, t));
          setPhase("error");
        }
      } finally {
        busyRef.current = false;
      }
    },
    [getToken, loadContext, loadPage, matterId, t, watchJob, onChanged],
  );

  useEffect(() => {
    const controller = new AbortController();
    lifetime.current = controller;
    setLoading(true);
    void (async () => {
      try {
        const [actor, session] = await Promise.all([
          getMe(getToken),
          getAgentSession(getToken, matterId),
        ]);
        if (controller.signal.aborted) return;
        identity.current = {
          actorId: actor.id,
          conversationId: session.activeConversationId,
        };
        const intent = readPendingOperationIntent(
          actor.id,
          matterId,
          "agent-send",
        );
        if (intent && session.activeConversationId) {
          try {
            const receipt = await getAgentSendReceipt(
              getToken,
              matterId,
              session.activeConversationId,
              intent.key,
            );
            if (controller.signal.aborted) return;
            if (
              receipt?.sendKey === intent.key &&
              receipt.matterId === matterId &&
              receipt.conversationId === session.activeConversationId &&
              receipt.jobId
            )
              clearManualIntent(intent);
          } catch {
            // Acceptance remains ambiguous; preserve the same key for a transport retry.
          }
        }
        await Promise.all([loadPage(), loadContext()]);
        const latest = await getLatestAgentJob(getToken, matterId);
        if (controller.signal.aborted) return;
        if (latest && latest.state !== "succeeded") {
          const send: PendingSend = {
            content: "",
            idempotencyKey: "",
            ...(isTerminalJobState(latest.state)
              ? { retryJobId: latest.jobId }
              : { watchJobId: latest.jobId }),
          };
          pendingSend.current = send;
          setJob(latest);
          if (isTerminalJobState(latest.state)) {
            if (!retryable(latest)) pendingSend.current = null;
            setError(
              t(
                latest.toolCallCount > 0
                  ? "turnFailedAfterTools"
                  : "turnFailed",
              ),
            );
            setPhase("error");
          } else void runSend(send);
        }
      } catch (cause: unknown) {
        if (!controller.signal.aborted) setError(describe(cause, t));
      } finally {
        if (!controller.signal.aborted) setLoading(false);
      }
    })();
    return () => controller.abort();
  }, [getToken, matterId, loadPage, loadContext, runSend, t]);

  const busy = phase === "sending" || phase === "running";
  const onSubmit = useCallback(async () => {
    const content = draft.trim();
    const owner = identity.current;
    if (!content || busyRef.current || !owner || loading) return;
    busyRef.current = true;
    try {
      const intent = await pendingOperationIntent(
        owner.actorId,
        matterId,
        "agent-send",
        {
          content,
          conversationId: owner.conversationId,
          ...(legalSelection ?? {}),
        },
      );
      if (lifetime.current?.signal.aborted) return;
      const send = {
        content,
        idempotencyKey: intent.key,
        intent,
        selection: legalSelection,
      };
      pendingSend.current = send;
      setDraft("");
      busyRef.current = false;
      void runSend(send);
    } catch (cause: unknown) {
      setError(describe(cause, t));
      busyRef.current = false;
    }
  }, [draft, loading, matterId, runSend, t, legalSelection]);

  const startFresh = useCallback(async () => {
    if (busyRef.current || !window.confirm(t("newConversationConfirm"))) return;
    busyRef.current = true;
    setPhase("sending");
    setError(null);
    try {
      const conversation = await startAgentConversation(getToken, matterId);
      if (identity.current) identity.current.conversationId = conversation.id;
      pendingSend.current = null;
      setActions({});
      setJob(null);
      setPhase("idle");
      setMessages([]);
      setNextCursor(null);
      setSelectedCitation(null);
      setDraft("");
    } catch (cause: unknown) {
      setError(describe(cause, t));
    } finally {
      busyRef.current = false;
      setPhase("idle");
    }
  }, [getToken, matterId, t]);

  const decide = useCallback(
    async (actionId: string, confirm: boolean) => {
      setActionBusy(actionId);
      setError(null);
      try {
        if (confirm) await confirmAgentAction(getToken, matterId, actionId);
        else await rejectAgentAction(getToken, matterId, actionId);
        await loadContext();
      } catch (cause: unknown) {
        setError(describe(cause, t));
      } finally {
        try {
          await loadPage();
        } catch (cause: unknown) {
          setError(describe(cause, t));
        }
        onChanged?.();
        setActionBusy(null);
      }
    },
    [getToken, loadContext, loadPage, matterId, t, onChanged],
  );

  const selectCitation = (citation: LegalSourceSelection) => {
    setSelectedCitation(citation);
    setContextOpen(true);
    // On wide screens the evidence shows in the side panel, so open it if it was folded away.
    setPanelCollapsed(false);
  };

  const sidePanel = (
    <ContextPanel
      context={context}
      matterId={matterId}
      selectedCitation={selectedCitation}
      onSelectCitation={selectCitation}
      onClearCitation={() => setSelectedCitation(null)}
      onCollapse={() => setPanelCollapsed(true)}
      t={t}
    />
  );

  return (
    <>
      <div aria-live="polite" className="sr-only">
        {busy ? t("working") : ""}
      </div>
      <div
        className={cn(
          "relative grid xl:grid-cols-[minmax(0,1fr)_auto]",
          !embedded && "min-h-[calc(100vh-260px)]",
        )}
      >
        <div className="flex min-w-0 flex-col">
          {/* Below xl the side panel folds into a row at the top, under the tabs, as Research's conversation rail does. */}
          <div className="border-border bg-surface border-b p-2 xl:hidden">
            <ContextRail
              context={context}
              matterId={matterId}
              onExpand={() => setContextOpen(true)}
              orientation="row"
              t={t}
            />
          </div>
          {/* Inside a matter this title row sits on the page, under the tabs, like every other section's. */}
          <PageHeader
            headingLevel={embedded ? "h2" : "h1"}
            title={t("title")}
            description={t("workspaceSubtitle")}
            action={
              <>
                {embedded && (
                  <Link
                    href={`/matters/${matterId}/assistant`}
                    className="text-forest text-sm underline"
                  >
                    {t("fullView")}
                  </Link>
                )}
                <Button
                  type="button"
                  variant="primary"
                  disabled={busy || loading}
                  onClick={() => void startFresh()}
                >
                  <Plus className="size-4" strokeWidth={1.5} />
                  {t("newConversation")}
                </Button>
              </>
            }
          />
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
                      matterId={matterId}
                      onCitation={selectCitation}
                      t={t}
                    />
                    {message.pendingActionId && (
                      <ProposalCard
                        action={actions[message.pendingActionId]}
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
                className="border-amber bg-amber-bg text-amber-text rounded-card mb-3 flex items-start gap-3 border p-3 text-sm"
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
            <LegalTransactionSelector
              matterId={matterId}
              value={legalSelection}
              onChange={setLegalSelection}
              disabled={busy || loading}
            />
            <Composer
              busy={busy || loading}
              draft={draft}
              onChange={setDraft}
              onSubmit={onSubmit}
              t={t}
            />
          </div>
        </div>
        <aside
          aria-label={t("caseContext")}
          data-collapsed={panelCollapsed || undefined}
          className={cn(
            "border-border bg-surface hidden border-l xl:block",
            panelCollapsed ? "w-14 p-2" : "w-[360px]",
          )}
        >
          {panelCollapsed ? (
            <ContextRail
              context={context}
              matterId={matterId}
              onExpand={() => setPanelCollapsed(false)}
              t={t}
            />
          ) : (
            sidePanel
          )}
        </aside>
        {/* Narrow screens: the panel slides in from the right over the section, below the
            matter's header and tabs (the level the wide panel starts at), as Research's
            conversations slide in under its page header. It stays mounted so it can
            animate; while closed it is invisible, so nothing in it can be focused. */}
        <div
          aria-hidden={!contextOpen}
          className={cn(
            "absolute inset-0 z-20 overflow-hidden xl:hidden",
            contextOpen ? "visible" : "invisible",
          )}
        >
          <button
            type="button"
            tabIndex={-1}
            aria-label={t("collapseContext")}
            className={cn(
              "bg-scrim absolute inset-0 transition-opacity duration-200 motion-reduce:transition-none",
              contextOpen ? "opacity-100" : "opacity-0",
            )}
            onClick={() => setContextOpen(false)}
          />
          <div
            ref={dialogRef}
            tabIndex={-1}
            role="dialog"
            aria-modal="true"
            aria-label={t("caseContext")}
            className={cn(
              "border-border bg-surface shadow-popover absolute inset-y-0 right-0 w-[min(340px,88vw)] overflow-y-auto border-l transition-transform duration-200 ease-out motion-reduce:transition-none",
              contextOpen ? "translate-x-0" : "translate-x-full",
            )}
          >
            <ContextPanel
              context={context}
              matterId={matterId}
              selectedCitation={selectedCitation}
              onSelectCitation={selectCitation}
              onClearCitation={() => setSelectedCitation(null)}
              onCollapse={() => setContextOpen(false)}
              t={t}
            />
          </div>
        </div>
      </div>
    </>
  );
}

function MessageRow({
  message,
  matterId,
  onCitation,
  t,
}: {
  message: ApiAgentMessage;
  matterId: string;
  onCitation: (citation: LegalSourceSelection) => void;
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
            {message.legalContext?.visibility === "current-policy-unavailable"
              ? t("legalHistoryUnavailable")
              : renderCitedText(
                  message.content,
                  message.citations,
                  (citation) =>
                    onCitation({
                      ...citation,
                      legalContext: message.legalContext,
                    }),
                  t,
                )}
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
                  onClick={() =>
                    onCitation({
                      ...citation,
                      legalContext: message.legalContext,
                    })
                  }
                >
                  [{index + 1}] {citation.label}
                </button>
              ))}
            </div>
          )}
          {assistant && message.legalContext?.kind === "result" && (
            <LegalResultContext
              context={message.legalContext}
              matterId={matterId}
              onSelect={onCitation}
            />
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
  t: ReturnType<typeof useTranslations>,
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
        aria-label={`${citation.label}, ${t(`verification.${citation.verificationStatus}`)}`}
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
    <div className="bg-canvas sticky bottom-0 pb-3 pt-2">
      <ChatComposer
        id="matter-assistant-composer"
        label={t("composerLabel")}
        placeholder={t("composerPlaceholder")}
        value={draft}
        onChange={onChange}
        onSubmit={onSubmit}
        sendLabel={t("send")}
        busyLabel={t("working")}
        busy={busy}
      />
      <p className="text-muted-ink mt-2 px-5 text-xs">{t("composerNotice")}</p>
    </div>
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

const PANEL_KEY = "draftly-assistant-context";

/** Whether the wide-screen context panel is folded to its icon rail: folded unless this browser last left it open. */
function usePanelCollapsed(): [boolean, (next: boolean) => void] {
  const [collapsed, setCollapsed] = useState(true);
  useEffect(() => {
    try {
      setCollapsed(window.localStorage.getItem(PANEL_KEY) !== "open");
    } catch {
      // Storage can be unavailable (private mode); the panel then simply starts folded.
    }
  }, []);
  const update = useCallback((next: boolean) => {
    setCollapsed(next);
    try {
      window.localStorage.setItem(PANEL_KEY, next ? "collapsed" : "open");
    } catch {
      // Not remembered; the choice still applies for this visit.
    }
  }, []);
  return [collapsed, update];
}

function contextMetrics(
  context: MatterContext | null,
  matterId: string,
  t: ReturnType<typeof useTranslations>,
) {
  return [
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
}

/** The icon-button look, for the rail's links. */
const RAIL_ITEM =
  "inline-flex size-10 shrink-0 items-center justify-center rounded-control border border-transparent text-ink hover:border-border hover:bg-hover-bg active:bg-active-bg [@media(pointer:coarse)]:size-11";

/**
 * The folded panel, as Research's conversation rail is on the left: the open
 * button on top, then one icon per section, each a link named in its tooltip
 * and for screen readers.
 */
function ContextRail({
  context,
  matterId,
  onExpand,
  orientation = "column",
  t,
}: {
  context: MatterContext | null;
  matterId: string;
  onExpand: () => void;
  /** A column beside the thread on wide screens; a row above it on narrow ones. */
  orientation?: "column" | "row";
  t: ReturnType<typeof useTranslations>;
}) {
  const open = (
    <IconButton
      label={t("expandContext")}
      aria-expanded={false}
      onClick={onExpand}
    >
      <PanelRightOpen className="size-5" strokeWidth={1.5} />
    </IconButton>
  );
  const links = contextMetrics(context, matterId, t).map(
    ({ icon: Icon, label, value, href }) => (
      <Link
        key={label}
        href={href}
        aria-label={`${label}: ${value}`}
        title={`${label}: ${value}`}
        className={RAIL_ITEM}
      >
        <Icon aria-hidden="true" className="size-5" strokeWidth={1.5} />
      </Link>
    ),
  );
  // The panel opens from the right, so the row sits on the right with its open
  // button at the far end, next to where the panel appears. DOM order follows
  // the visual order, so focus moves the way the eye does.
  return orientation === "column" ? (
    <div className="sticky top-2 flex flex-col items-center gap-1">
      {open}
      {links}
    </div>
  ) : (
    <div className="flex items-center justify-end gap-1">
      {links}
      {open}
    </div>
  );
}

function ContextPanel({
  context,
  matterId,
  selectedCitation,
  onClearCitation,
  onSelectCitation,
  onCollapse,
  t,
}: {
  context: MatterContext | null;
  matterId: string;
  selectedCitation: LegalSourceSelection | null;
  onClearCitation: () => void;
  onSelectCitation: (citation: LegalSourceSelection) => void;
  /** Wide screens only: fold the panel back to its rail. */
  onCollapse?: () => void;
  t: ReturnType<typeof useTranslations>;
}) {
  const collapse = onCollapse ? (
    <IconButton
      label={t("collapseContext")}
      aria-expanded
      className="size-8"
      onClick={onCollapse}
    >
      <PanelRightClose className="size-4" strokeWidth={1.5} />
    </IconButton>
  ) : null;
  const tNav = useTranslations("matterNav");
  const getToken = useTokenProvider();
  const [original, setOriginal] = useState<string | null>(null);
  const [sourceError, setSourceError] = useState(false);
  useEffect(() => {
    setOriginal(null);
    setSourceError(false);
  }, [selectedCitation]);
  const openOriginal = async () => {
    const sourceId = selectedCitation?.sourceFileId;
    if (!sourceId) return;
    try {
      const source = await getSourceFile(getToken, sourceId);
      if (source.matterId !== matterId) throw new Error("Source unavailable");
      setOriginal(sourceId);
    } catch {
      setSourceError(true);
    }
  };
  if (selectedCitation)
    return (
      <div className="p-5">
        <div className="flex items-center justify-between gap-2">
          <button
            type="button"
            className="text-forest text-sm hover:underline"
            onClick={onClearCitation}
          >
            {t("backToContext")}
          </button>
          {collapse}
        </div>
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
          <LegalAuthorityPanel
            selection={selectedCitation}
            matterId={matterId}
            onSelect={onSelectCitation}
          />
          {selectedCitation.passage && (
            <div className="mt-3">
              <p className="text-muted-ink text-xs">{t("matchedSource")}</p>
              <p className="text-muted-ink text-xs">
                {t("legalPassagePage", {
                  page: selectedCitation.page ?? t("legalUnknown"),
                })}
              </p>
              <blockquote className="mt-1 whitespace-pre-wrap text-sm">
                {selectedCitation.passage}
              </blockquote>
            </div>
          )}
          {selectedCitation.corpusVersion && (
            <p className="text-muted-ink mt-2 break-words text-xs">
              {t("sourceVersion", { version: selectedCitation.corpusVersion })}
            </p>
          )}
          {["statute", "amendment", "gazette", "case"].includes(
            selectedCitation.sourceType,
          ) &&
            !selectedCitation.passage && (
              <p className="mt-3 text-sm">{t("sourceUnavailable")}</p>
            )}
          {selectedCitation.sourceFileId && (
            <Button variant="secondary" onClick={() => void openOriginal()}>
              {t("openSource")}
            </Button>
          )}
          {sourceError && <p role="alert">{t("sourceUnavailable")}</p>}
          {original === selectedCitation.sourceFileId && original && (
            <SourceFilePreview
              getToken={getToken}
              matterId={matterId}
              sourceFileId={original}
              pageStart={selectedCitation.page ?? 1}
              pageEnd={selectedCitation.page ?? 1}
            />
          )}
          {!selectedCitation.sourceFileId &&
            !["statute", "amendment", "gazette", "case"].includes(
              selectedCitation.sourceType,
            ) && (
              <Link
                href={citationHref(matterId, selectedCitation)}
                className="text-forest mt-4 inline-flex items-center gap-1 text-sm font-medium hover:underline"
              >
                {t("openSource")}
                <ChevronRight className="size-4" />
              </Link>
            )}
        </div>
      </div>
    );
  const metrics = contextMetrics(context, matterId, t);
  return (
    <div>
      <div className="border-border border-b p-5">
        <div className="flex items-center justify-between gap-2">
          <div className="text-muted-ink text-xs font-semibold">
            {t("caseContext")}
          </div>
          {collapse}
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
  action,
  busy,
  onConfirm,
  onReject,
  t,
}: {
  action?: ApiPendingAction;
  busy: boolean;
  onConfirm: () => void;
  onReject: () => void;
  t: ReturnType<typeof useTranslations>;
}) {
  const reviewLabel = useTranslations("enums.requirementStatus");
  return (
    <div
      className="border-amber bg-amber-bg rounded-card ml-12 mt-3 border p-4"
      data-testid="proposal-card"
    >
      <p className="text-sm font-semibold">{t("proposalTitle")}</p>
      {!action && <p className="mt-2 text-sm">{t("proposalUnavailable")}</p>}
      {action && (
        <>
          <p className="mt-2 text-sm">{t(`actionState.${action.state}`)}</p>
          <p className="mt-2 text-sm font-medium">
            {t(`actionKind.${action.actionKind}`)}
          </p>
          <dl className="mt-2 space-y-2 text-sm">
            <div>
              <dt className="text-muted-ink">{t("proposalTarget")}</dt>
              <dd className="break-all">
                {action.targetRef} ·{" "}
                {t("proposalVersion", { version: action.targetVersion })}
              </dd>
            </div>
            {proposalDetails(action, (value) =>
              isDigitalReviewStatus(value)
                ? reviewLabel(value)
                : t("reviewStatusUnknown"),
            ).map(([label, value]) => (
              <div key={label}>
                <dt className="text-muted-ink">
                  {t(`proposalFields.${label}`)}
                </dt>
                <dd className="whitespace-pre-wrap break-words">{value}</dd>
              </div>
            ))}
          </dl>
          {Object.entries(action.result ?? {})
            .filter(([key]) =>
              ["factId", "itemId", "linkId", "version"].includes(key),
            )
            .map(([key, value]) => (
              <p key={key} className="mt-2 break-all text-sm">
                {t("resultRecord")}: {String(value)}
              </p>
            ))}
        </>
      )}
      {action?.state === "proposed" && (
        <>
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
        </>
      )}
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
    statute: "",
    amendment: "",
    gazette: "",
    case: "",
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
    if (cause.code === "agent_retry_unavailable") return t("errorRetry");
    return apiErrorMessage(cause, t("errorUnknown"));
  }
  return t("errorUnknown");
}

function isDigitalReviewStatus(value: string): value is DigitalReviewStatus {
  return (
    [
      "UNREVIEWED",
      "AI_ORGANIZED",
      "LAWYER_CONFIRMED",
      "REJECTED",
      "SUPERSEDED",
    ] satisfies DigitalReviewStatus[]
  ).some((status) => status === value);
}
function proposalDetails(
  action: ApiPendingAction,
  reviewLabel: (value: string) => string,
): [string, string][] {
  const args = action.arguments;
  const reviewed =
    args.reviewed && typeof args.reviewed === "object"
      ? (args.reviewed as Record<string, unknown>)
      : {};
  const rows = { ...args, ...reviewed };
  const fields = [
    "factValue",
    "transactionId",
    "subjectId",
    "digitalReview",
    "detectedDocumentId",
    "documentVersion",
    "interpretationGeneration",
    "resolveFactIds",
    "evidenceReferenceIds",
    "reason",
  ];
  return fields.flatMap((field) =>
    rows[field] == null
      ? []
      : [
          [
            field,
            field === "digitalReview"
              ? reviewLabel(String(rows[field]))
              : typeof rows[field] === "object"
                ? JSON.stringify(rows[field])
                : String(rows[field]),
          ] as [string, string],
        ],
  );
}

function retryable(job: ApiAgentJob) {
  return (
    job.state === "failed" &&
    job.failureClass === "model_unavailable" &&
    job.toolCallCount === 0
  );
}
