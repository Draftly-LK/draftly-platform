"use client";

/**
 * Matter assistant — one fixed thread per matter.
 *
 * The loop this screen owns: send a message, watch the turn, show what the
 * assistant proposed, and let a lawyer confirm or reject it. Nothing the
 * assistant suggests changes the matter until someone presses Confirm.
 *
 * Three deliberate behaviours:
 *
 * - **Retry never duplicates.** The idempotency key is minted once per logical
 *   send and reused on retry, so a failed network call replays the same job.
 * - **Progress degrades, it does not break.** SSE is attempted first; if the
 *   stream cannot open, polling takes over and the user sees no difference.
 * - **Unverified is labelled.** A proposal card says plainly that nothing has
 *   changed yet, because the distinction between a suggestion and a decision
 *   is the whole point of the product.
 */

import { useCallback, useEffect, useRef, useState } from "react";
import { useTranslations } from "next-intl";
import { ApiError } from "@/lib/api/client";
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
import { useTokenProvider } from "@/lib/api/use-token-provider";

const PAGE_SIZE = 20;
const POLL_INTERVAL_MS = 1200;

type Phase = "idle" | "sending" | "running" | "error";

interface PendingSend {
  content: string;
  /** Minted once and reused, so a retry replays rather than duplicates. */
  idempotencyKey: string;
}

interface Props {
  matterId: string;
}

export function AssistantScreen({ matterId }: Props) {
  const t = useTranslations("assistant");
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

  /** Watch a turn: stream if we can, poll if we cannot. */
  const watchJob = useCallback(
    async (jobId: string) => {
      // Stream first; fall back to polling when the stream cannot be used.
      // Either way the job row settles it, so the two cannot disagree.
      const streamed = await streamAgentJobEvents(getToken, jobId, () => {});
      for (let attempt = 0; attempt < (streamed ? 1 : 40); attempt += 1) {
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

  const onSubmit = useCallback(
    (event: React.FormEvent) => {
      event.preventDefault();
      const content = draft.trim();
      if (!content || phase === "sending" || phase === "running") return;
      const send: PendingSend = {
        content,
        idempotencyKey: newIdempotencyKey(),
      };
      pendingSend.current = send;
      setDraft("");
      void runSend(send);
    },
    [draft, phase, runSend],
  );

  const onRetry = useCallback(() => {
    const send = pendingSend.current;
    if (send) void runSend(send);
  }, [runSend]);

  const decide = useCallback(
    async (actionId: string, confirm: boolean) => {
      setActionBusy(actionId);
      setError(null);
      try {
        if (confirm) {
          await confirmAgentAction(getToken, matterId, actionId);
        } else {
          await rejectAgentAction(getToken, matterId, actionId);
        }
        await loadPage();
      } catch (cause: unknown) {
        setError(describe(cause, t));
      } finally {
        setActionBusy(null);
      }
    },
    [getToken, loadPage, matterId, t],
  );

  const busy = phase === "sending" || phase === "running";

  return (
    <section className="flex h-full flex-col gap-4" aria-label={t("title")}>
      <header>
        <h1 className="font-serif text-xl">{t("title")}</h1>
        <p className="text-sm text-muted">{t("subtitle")}</p>
      </header>

      <ol
        className="flex flex-1 flex-col-reverse gap-3 overflow-y-auto"
        aria-live="polite"
        aria-busy={busy}
        data-testid="assistant-transcript"
      >
        {messages.map((message) => (
          <li key={message.id} data-role={message.role}>
            <MessageBubble message={message} t={t} />
            {message.pendingActionId ? (
              <ProposalCard
                actionId={message.pendingActionId}
                busy={actionBusy === message.pendingActionId}
                onConfirm={() => decide(message.pendingActionId!, true)}
                onReject={() => decide(message.pendingActionId!, false)}
                t={t}
              />
            ) : null}
          </li>
        ))}
        {loading ? <li className="text-sm text-muted">{t("loading")}</li> : null}
      </ol>

      {nextCursor ? (
        <button
          type="button"
          className="self-start text-sm underline"
          onClick={() => void loadPage(nextCursor)}
        >
          {t("loadOlder")}
        </button>
      ) : null}

      {busy ? (
        <p className="text-sm text-muted" role="status">
          {job ? t("working") : t("sending")}
        </p>
      ) : null}

      {error ? (
        <div role="alert" className="rounded border border-strong p-3 text-sm">
          <p>{error}</p>
          {pendingSend.current ? (
            <button type="button" className="mt-2 underline" onClick={onRetry}>
              {t("retry")}
            </button>
          ) : null}
        </div>
      ) : null}

      <form onSubmit={onSubmit} className="flex gap-2">
        <label className="sr-only" htmlFor="assistant-composer">
          {t("composerLabel")}
        </label>
        <textarea
          id="assistant-composer"
          className="flex-1 rounded border border-strong p-2"
          rows={2}
          value={draft}
          disabled={busy}
          onChange={(event) => setDraft(event.target.value)}
          placeholder={t("composerPlaceholder")}
        />
        <button
          type="submit"
          className="rounded border border-strong px-4"
          disabled={busy || draft.trim().length === 0}
        >
          {t("send")}
        </button>
      </form>
    </section>
  );
}

function MessageBubble({
  message,
  t,
}: {
  message: ApiAgentMessage;
  t: ReturnType<typeof useTranslations>;
}) {
  const isAssistant = message.role === "assistant";
  return (
    <article className="rounded border border-strong p-3">
      <p className="text-xs uppercase tracking-wide text-muted">
        {isAssistant ? t("roleAssistant") : t("roleYou")}
      </p>
      <p className="whitespace-pre-wrap text-sm">{message.content}</p>
      {isAssistant ? (
        <p className="mt-1 text-xs text-muted">{t("unverifiedNotice")}</p>
      ) : null}
    </article>
  );
}

function ProposalCard({
  actionId,
  busy,
  onConfirm,
  onReject,
  t,
}: {
  actionId: string;
  busy: boolean;
  onConfirm: () => void;
  onReject: () => void;
  t: ReturnType<typeof useTranslations>;
}) {
  return (
    <div
      className="mt-2 rounded border border-strong p-3"
      data-testid="proposal-card"
      data-action-id={actionId}
    >
      <p className="text-sm font-medium">{t("proposalTitle")}</p>
      {/* Said plainly: a card is a suggestion until a human acts on it. */}
      <p className="text-xs text-muted">{t("proposalNothingChanged")}</p>
      <div className="mt-2 flex gap-2">
        <button
          type="button"
          className="rounded border border-strong px-3 text-sm"
          disabled={busy}
          onClick={onConfirm}
        >
          {t("confirm")}
        </button>
        <button
          type="button"
          className="rounded border border-strong px-3 text-sm"
          disabled={busy}
          onClick={onReject}
        >
          {t("reject")}
        </button>
      </div>
    </div>
  );
}

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

/** Map a backend error code to a message the lawyer can act on. */
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
