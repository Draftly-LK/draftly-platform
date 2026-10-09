"use client";

import { useCallback, useEffect, useId, useRef, useState } from "react";
import { useTranslations } from "next-intl";
import Link from "next/link";
import { Clock3, Plus, RefreshCw } from "lucide-react";
import { Button, buttonClass } from "@/components/ui/button";
import {
  ApiError,
  apiErrorMessage,
  type TokenProvider,
} from "@/lib/api/client";
import { getMe } from "@/lib/api/auth";
import {
  createWorkTask,
  decideTaskSuggestion,
  decideWorkTask,
  getWorkChecklist,
} from "@/lib/api/work-checklist";
import {
  clearManualIntent,
  pendingOperationIntent,
  type ManualIntent,
} from "@/lib/api/mutation-intent";
import {
  MATTER_WORK_CHANGED,
  notifyMatterWorkChanged,
} from "@/lib/matter-work-events";
import {
  WorkTaskRow,
  WorkEvidenceLinks,
  taskHref,
  workControl,
} from "./work-checklist-task";
import { humanizeMessageKey } from "@/lib/i18n/humanize";
import type {
  WorkChecklistRead,
  WorkEvidenceReference,
  WorkTask,
  WorkTaskGroup,
  WorkTaskState,
} from "@/types/work-checklist";

const groups: WorkTaskGroup[] = [
  "documents",
  "evidence",
  "drafting",
  "execution",
  "registration",
  "completion",
];
const finished: WorkTaskState[] = ["complete", "not-applicable", "cancelled"];
const control = workControl;
export function WorkChecklist({
  matterId,
  getToken,
}: {
  matterId: string;
  getToken: TokenProvider;
}) {
  const t = useTranslations("workChecklist");
  const root = useTranslations();
  const id = useId();
  const [data, setData] = useState<WorkChecklistRead | null>(null);
  const [loading, setLoading] = useState(true);
  const [unavailable, setUnavailable] = useState(false);
  const [busy, setBusy] = useState(false);
  const [changed, setChanged] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState("");
  const [adding, setAdding] = useState(false);
  const [title, setTitle] = useState("");
  const [reason, setReason] = useState("");
  const [activeTaskId, setActiveTaskId] = useState<string | null>(null);
  const [group, setGroup] = useState<WorkTaskGroup>("documents");
  const alive = useRef(true);
  const requests = useRef(0);
  const scope = useRef(matterId);
  const pending = useRef<ManualIntent | null>(null);
  const saving = useRef(false);
  const titleOf = (task: WorkTask) =>
    task.titleKey && root.has(task.titleKey)
      ? root(task.titleKey)
      : (task.title ??
        (task.titleKey ? humanizeMessageKey(task.titleKey) : t("untitled")));
  const reasonOf = (task: WorkTask) =>
    task.reasonKey && root.has(task.reasonKey)
      ? root(task.reasonKey)
      : (task.reason ??
        (task.reasonKey
          ? humanizeMessageKey(task.reasonKey)
          : t("reasonUnknown")));
  const load = useCallback(async () => {
    const request = ++requests.current;
    setLoading(true);
    try {
      const packet = await getWorkChecklist(getToken, matterId);
      if (
        !alive.current ||
        scope.current !== matterId ||
        requests.current !== request
      )
        return;
      setData(packet);
      setUnavailable(false);
    } catch (cause) {
      if (
        !alive.current ||
        scope.current !== matterId ||
        requests.current !== request
      )
        return;
      setUnavailable(true);
      setError(apiErrorMessage(cause, t("unavailable")));
    } finally {
      if (
        alive.current &&
        scope.current === matterId &&
        requests.current === request
      )
        setLoading(false);
    }
  }, [getToken, matterId, t]);
  useEffect(() => {
    alive.current = true;
    scope.current = matterId;
    setData(null);
    setError(null);
    void load();
    const refresh = (event: Event) => {
      if (
        (event as CustomEvent<{ matterId: string }>).detail?.matterId ===
          matterId &&
        !saving.current
      )
        void load();
    };
    window.addEventListener(MATTER_WORK_CHANGED, refresh);
    return () => {
      alive.current = false;
      window.removeEventListener(MATTER_WORK_CHANGED, refresh);
    };
  }, [load, matterId]);
  const refresh = async () => {
    if (busy) return;
    // Refresh never discards an uncertain write. Only an explicit renewal of
    // a rejected precondition may mint a new logical decision.
    if (changed && pending.current) {
      clearManualIntent(pending.current);
      pending.current = null;
    }
    setChanged(false);
    setError(null);
    setNotice("");
    await load();
  };
  const perform = async (
    operation: string,
    body: unknown,
    version: number | undefined,
    command: (key: string, pinnedVersion?: number) => Promise<unknown>,
  ) => {
    if (saving.current || changed || unavailable || loading) return false;
    saving.current = true;
    setBusy(true);
    setError(null);
    setNotice("");
    try {
      const actor = await getMe(getToken);
      const intent = await pendingOperationIntent(
        actor.id,
        matterId,
        operation,
        body,
        version,
      );
      pending.current = intent;
      if (!intent.persistent) setNotice(t("retryStorage"));
      await command(intent.key, intent.expectedVersion);
      clearManualIntent(intent);
      pending.current = null;
      if (!alive.current || scope.current !== matterId) return false;
      setNotice(t("saved"));
      notifyMatterWorkChanged(matterId);
      await load();
      return true;
    } catch (cause) {
      if (!alive.current || scope.current !== matterId) return false;
      const conflict =
        cause instanceof ApiError && [409, 412].includes(cause.status);
      setChanged(conflict);
      setError(
        conflict ? t("changed") : apiErrorMessage(cause, t("saveFailed")),
      );
      return false;
    } finally {
      saving.current = false;
      if (alive.current && scope.current === matterId) setBusy(false);
    }
  };
  const decide = (
    task: WorkTask,
    decision: "complete" | "review" | "cancel",
    note: string,
    evidence?: WorkEvidenceReference[],
  ) => {
    const body = {
      decision,
      ...(evidence === undefined ? {} : { evidence }),
      ...(note.trim() ? { note: note.trim() } : {}),
    };
    return perform(
      `work-task:${task.id}:decision`,
      body,
      task.version,
      (key, version) =>
        decideWorkTask(
          getToken,
          matterId,
          task.id,
          body,
          version ?? task.version,
          key,
        ),
    );
  };
  const suggestion = (task: WorkTask, decision: "accept" | "dismiss") =>
    perform(
      `work-suggestion:${task.id}`,
      { decision },
      task.version,
      (key, version) =>
        decideTaskSuggestion(
          getToken,
          matterId,
          task.id,
          decision,
          version ?? task.version,
          key,
        ),
    );
  const disabled = busy || loading || changed || unavailable;
  const next = data?.tasks.find((task) => task.id === data.nextTaskId);
  const nextHref = next ? taskHref(matterId, next) : null;
  const completed =
    data?.tasks.filter((task) => finished.includes(task.state)) ?? [];
  const row = (task: WorkTask) => (
    <WorkTaskRow
      key={task.id}
      task={task}
      matterId={matterId}
      getToken={getToken}
      title={titleOf(task)}
      reason={reasonOf(task)}
      disabled={disabled}
      active={activeTaskId === task.id}
      onDecision={decide}
    />
  );
  return (
    <section
      aria-labelledby={`${id}-heading`}
      className="border-border bg-surface rounded-card overflow-hidden border"
    >
      <div className="border-border space-y-4 border-b p-4 sm:p-5">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <h2 id={`${id}-heading`} className="text-lg font-semibold">
            {t("heading")}
          </h2>
          <div className="flex flex-wrap gap-2">
            <Button
              size="sm"
              disabled={disabled}
              onClick={() => setAdding(!adding)}
              aria-expanded={adding}
            >
              <Plus aria-hidden="true" className="size-4" />
              {t("add")}
            </Button>
            <Button size="sm" disabled={busy} onClick={() => void refresh()}>
              <RefreshCw aria-hidden="true" className="size-4" />
              {t("refresh")}
            </Button>
          </div>
        </div>
        {loading && (
          <p role="status" className="text-muted-ink text-sm">
            {t("loading")}
          </p>
        )}
        {error && (
          <p role="alert" className="text-red text-sm">
            {error}
          </p>
        )}
        {notice && (
          <p role="status" className="text-muted-ink text-sm">
            {notice}
          </p>
        )}
        {data && !unavailable && !loading && (
          <div className="space-y-2">
            <p className="font-medium">
              {data.progress.total > 0
                ? t("progress", {
                    total: data.progress.total,
                    completed: data.progress.completed,
                    percent: data.progress.percent,
                  })
                : t("noApplicable")}
            </p>
            {data.progress.total > 0 && (
              <progress
                aria-label={t("progressLabel")}
                max={100}
                value={data.progress.percent}
                className="accent-forest rounded-control h-2 w-full overflow-hidden"
              />
            )}
            {data.progress.assessing && (
              <p className="text-amber-text flex items-center gap-2 text-sm">
                <Clock3 aria-hidden="true" className="size-4" />
                {t("assessing")}
              </p>
            )}
            <p className="text-muted-ink text-sm leading-6">
              {t("eligibility")}
            </p>
            {next && (
              <div className="bg-canvas flex flex-wrap items-center justify-between gap-3 rounded p-3">
                <p className="font-medium">
                  {t("next", { task: titleOf(next) })}
                </p>
                {!nextHref && (
                  <Button
                    disabled={disabled}
                    onClick={() => setActiveTaskId(next.id)}
                  >
                    {t("review")}
                  </Button>
                )}
                {nextHref && (
                  <Link href={nextHref} className={buttonClass("primary")}>
                    {t("review")}
                  </Link>
                )}
              </div>
            )}
          </div>
        )}
        {adding && (
          <form
            className="border-border space-y-3 rounded border p-3"
            onSubmit={(event) => {
              event.preventDefault();
              const body = {
                title: title.trim(),
                reason: reason.trim(),
                group,
              };
              void perform("work-task:create", body, undefined, (key) =>
                createWorkTask(getToken, matterId, body, key),
              ).then((saved) => {
                if (saved) {
                  setAdding(false);
                  setTitle("");
                  setReason("");
                }
              });
            }}
          >
            <label className="block space-y-1 text-sm">
              <span>{t("task")}</span>
              <input
                className={control}
                value={title}
                onChange={(event) => setTitle(event.target.value)}
                required
                maxLength={240}
                disabled={busy}
              />
            </label>
            <label className="block space-y-1 text-sm">
              <span>{t("reason")}</span>
              <textarea
                className={control}
                value={reason}
                onChange={(event) => setReason(event.target.value)}
                maxLength={4000}
                disabled={busy}
              />
            </label>
            <label className="block space-y-1 text-sm">
              <span>{t("group")}</span>
              <select
                className={control}
                value={group}
                onChange={(event) =>
                  setGroup(event.target.value as WorkTaskGroup)
                }
                disabled={busy}
              >
                {groups.map((item) => (
                  <option key={item} value={item}>
                    {t(`groups.${item}`)}
                  </option>
                ))}
              </select>
            </label>
            <div className="flex flex-wrap gap-2">
              <Button
                variant="primary"
                type="submit"
                disabled={disabled || !title.trim()}
              >
                {t("save")}
              </Button>
              <Button
                type="button"
                disabled={busy}
                onClick={() => setAdding(false)}
              >
                {t("close")}
              </Button>
            </div>
          </form>
        )}
      </div>
      {data && (
        <div className="space-y-5 p-4 sm:p-5">
          {data.suggestions.length > 0 && (
            <section className="border-border space-y-3 rounded border p-3">
              <h3 className="font-semibold">{t("suggestions")}</h3>
              <p className="text-muted-ink text-sm">{t("suggestionsNotice")}</p>
              {data.suggestions.map((task) => (
                <div
                  key={task.id}
                  className="border-border space-y-2 border-t pt-3"
                >
                  <p className="font-medium">{titleOf(task)}</p>
                  <p className="text-muted-ink text-xs">
                    {t("agentSuggestion")} · {t("awaitingAcceptance")}
                  </p>
                  <p className="text-muted-ink text-sm">{reasonOf(task)}</p>
                  <WorkEvidenceLinks
                    matterId={matterId}
                    evidence={task.evidence}
                  />
                  <div className="flex flex-wrap gap-2">
                    <Button
                      disabled={disabled}
                      onClick={() => void suggestion(task, "accept")}
                    >
                      {t("accept")}
                    </Button>
                    <Button
                      disabled={disabled}
                      onClick={() => void suggestion(task, "dismiss")}
                    >
                      {t("dismiss")}
                    </Button>
                  </div>
                </div>
              ))}
            </section>
          )}
          {groups.map((item) => {
            const tasks = data.tasks.filter(
              (task) => task.group === item && !finished.includes(task.state),
            );
            return (
              <section key={item} aria-labelledby={`${id}-${item}`}>
                <h3 id={`${id}-${item}`} className="mb-2 text-sm font-semibold">
                  {t(`groups.${item}`)}
                </h3>
                {tasks.length > 0 ? (
                  <div className="border-border divide-border divide-y rounded border">
                    {tasks.map(row)}
                  </div>
                ) : (
                  <p className="text-muted-ink text-sm">{t("noOutstanding")}</p>
                )}
              </section>
            );
          })}
          <details className="border-border rounded border">
            <summary className="cursor-pointer p-3 text-sm font-medium">
              {t("completed", { count: completed.length })}
            </summary>
            <div className="divide-border border-border divide-y border-t">
              {completed.map(row)}
            </div>
          </details>
        </div>
      )}
    </section>
  );
}
