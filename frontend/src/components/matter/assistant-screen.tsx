"use client";

/**
 * Matter assistant — one fixed thread per matter.
 *
 * Presentation deliberately mirrors `components/assistant/assistant-screen.tsx`
 * (the research chat): same card, composer, avatar tile and type scale, so the
 * two chat surfaces do not look like they came from different products.
 *
 * Three behaviours this screen owns:
 *
 * - **Retry never duplicates.** The idempotency key is minted once per logical
 *   send and reused, so a failed network call replays the same job.
 * - **Progress degrades.** SSE is attempted first; polling takes over silently
 *   when the stream cannot be used. The job row settles the outcome either way.
 * - **Unverified is labelled.** A proposal card states that nothing has changed
 *   yet, because the line between a suggestion and a decision is the product.
 */

import {
  AlertTriangle,
  Check,
  MessageCircleQuestion,
  RotateCcw,
  Send,
  Sparkles,
  X,
} from "lucide-react";
import { useTranslations } from "next-intl";
import { useCallback, useEffect, useRef, useState } from "react";
import { AppShell } from "@/components/shell/app-shell";
import { PageHeader } from "@/components/shell/page-header";
import { Button } from "@/components/ui/button";
import {
  confirmAgentAction,
  getAgentJob,
  isTerminalJobState,
  listAgentMessages,
  newIdempotencyKey,
  rejectAgentAction,
  sendAgentMessage,
  streamAgentJobEvents,
  type ApiAgentJob,
  type ApiAgentMessage,
} from "@/lib/api/agent";
import { ApiError } from "@/lib/api/client";
import { useTokenProvider } from "@/lib/api/use-token-provider";

const PAGE_SIZE = 20;
const POLL_INTERVAL_MS = 1200;
const MAX_POLLS = 40;

type Phase = "idle" | "sending" | "running" | "error";

interface PendingSend {
  content: string;
  idempotencyKey: string;
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
  const pendingSend = useRef<PendingSend | null>(null);

  const loadPage = useCallback(
    async (cursor?: string) => {
      const page = await listAgentMessages(getToken, matterId, {
        limit: PAGE_SIZE,
        cursor,
      });
      setMessages((previous) =>
        cursor ? [...previous, ...page.items] : page.items,
      );
      setNextCursor(page.page.hasMore ? page.page.nextCursor : null);
    },
    [getToken, matterId],
  );

  useEffect(() => {
    let active = true;
    setLoading(true);
    loadPage()
      .catch((cause: unknown) => {
        if (active) setError(describe(cause, t));
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [loadPage, t]);

  const watchJob = useCallback(
    async (jobId: string) => {
      const streamed = await streamAgentJobEvents(getToken, jobId, () => {});
      for (let attempt = 0; attempt < (streamed ? 1 : MAX_POLLS); attempt += 1) {
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
    [getToken, loadPage, matterId, t, watchJob],
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

  const decide = useCallback(
    async (actionId: string, confirm: boolean) => {
      setActionBusy(actionId);
      setError(null);
      try {
        if (confirm) await confirmAgentAction(getToken, matterId, actionId);
        else await rejectAgentAction(getToken, matterId, actionId);
        await loadPage();
      } catch (cause: unknown) {
        setError(describe(cause, t));
      } finally {
        setActionBusy(null);
      }
    },
    [getToken, loadPage, matterId, t],
  );

  return (
    <AppShell matterId={matterId}>
      <PageHeader title={t("title")} description={t("subtitle")} />
      <div aria-live="polite" className="sr-only">
        {busy ? t("working") : ""}
      </div>
      <main className="mx-auto min-w-0 max-w-3xl p-6">
        <form
          className="border-border-strong bg-surface shadow-popover rounded border p-3"
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
            className="min-h-24 w-full resize-y border-0 bg-transparent p-2 outline-none"
            placeholder={t("composerPlaceholder")}
            value={draft}
            disabled={busy}
            onChange={(event) => setDraft(event.target.value)}
          />
          <div className="border-border flex items-center gap-3 border-t pt-3">
            <p className="text-muted-ink text-xs">
              {busy ? (job ? t("working") : t("sending")) : t("unverifiedNotice")}
            </p>
            <Button
              type="submit"
              className="ml-auto"
              variant="primary"
              disabled={busy || draft.trim().length === 0}
            >
              {t("send")}
              <Send className="size-4" strokeWidth={1.5} />
            </Button>
          </div>
        </form>

        {error && (
          <div
            role="alert"
            className="border-border bg-surface mt-5 flex items-start gap-3 rounded-card border p-4 shadow-card"
          >
            <AlertTriangle
              className="text-amber-text size-5 shrink-0"
              strokeWidth={1.5}
            />
            <div className="min-w-0 flex-1">
              <p className="text-sm">{error}</p>
              {pendingSend.current && (
                <Button
                  type="button"
                  variant="secondary"
                  className="mt-3"
                  onClick={() => {
                    const send = pendingSend.current;
                    if (send) void runSend(send);
                  }}
                >
                  <RotateCcw className="size-4" strokeWidth={1.5} />
                  {t("retry")}
                </Button>
              )}
            </div>
          </div>
        )}

        <section aria-label={t("thread")} className="mt-6 space-y-4">
          {loading && <p className="text-muted-ink text-sm">{t("loading")}</p>}
          {!loading && messages.length === 0 && (
            <p className="text-muted-ink text-sm">{t("empty")}</p>
          )}
          {messages.map((message) => (
            <div key={message.id}>
              <MessageCard message={message} t={t} />
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
          {nextCursor && (
            <Button
              type="button"
              variant="secondary"
              onClick={() => void loadPage(nextCursor)}
            >
              {t("loadOlder")}
            </Button>
          )}
        </section>
      </main>
    </AppShell>
  );
}

function MessageCard({
  message,
  t,
}: {
  message: ApiAgentMessage;
  t: ReturnType<typeof useTranslations>;
}) {
  const isAssistant = message.role === "assistant";
  return (
    <article
      className="border-border-strong bg-surface rounded border"
      data-role={message.role}
    >
      <header className="flex items-start gap-3 px-5 py-4">
        <div className="bg-selected-bg text-forest grid size-9 shrink-0 place-items-center rounded">
          {isAssistant ? (
            <Sparkles className="size-5" strokeWidth={1.5} />
          ) : (
            <MessageCircleQuestion className="size-5" strokeWidth={1.5} />
          )}
        </div>
        <div className="min-w-0 flex-1">
          <div className="text-muted-ink text-xs font-semibold uppercase">
            {isAssistant ? t("roleAssistant") : t("roleYou")}
          </div>
          <p className="mt-1 leading-7 whitespace-pre-wrap">{message.content}</p>
        </div>
      </header>
    </article>
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
      className="border-border bg-surface mt-2 ml-12 rounded-card border p-4 shadow-card"
      data-testid="proposal-card"
    >
      <p className="text-sm font-semibold">{t("proposalTitle")}</p>
      {/* Status is never colour alone: icon plus text, per the design system. */}
      <p className="text-amber-text mt-1 flex items-center gap-2 text-xs">
        <AlertTriangle className="size-4 shrink-0" strokeWidth={1.5} />
        {t("proposalNothingChanged")}
      </p>
      <div className="mt-3 flex gap-2">
        <Button type="button" variant="primary" disabled={busy} onClick={onConfirm}>
          <Check className="size-4" strokeWidth={1.5} />
          {t("confirm")}
        </Button>
        <Button type="button" variant="secondary" disabled={busy} onClick={onReject}>
          <X className="size-4" strokeWidth={1.5} />
          {t("reject")}
        </Button>
      </div>
    </div>
  );
}

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

/** Map a backend error code to something the lawyer can act on. */
function describe(
  cause: unknown,
  t: ReturnType<typeof useTranslations>,
): string {
  if (cause instanceof ApiError) {
    switch (cause.code) {
      case "pending_action_stale":
        return t("errorStale");
      case "capability_denied":
        return t("errorCapability");
      case "matter_agent_disabled":
        return t("errorDisabled");
      case "agent_model_unavailable":
        return t("errorProvider");
      default:
        return cause.message;
    }
  }
  return t("errorUnknown");
}
