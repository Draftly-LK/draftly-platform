"use client";

import { useEffect, useId, useRef, useState } from "react";
import { useTranslations } from "next-intl";
import Link from "next/link";
import {
  AlertCircle,
  CheckCircle2,
  Circle,
  Clock3,
  FileText,
} from "lucide-react";
import { Button, buttonClass } from "@/components/ui/button";
import { apiErrorMessage, type TokenProvider } from "@/lib/api/client";
import { getWorkTaskHistory } from "@/lib/api/work-checklist";
import { getCompleteDocumentInbox } from "@/lib/api/documents";
import type {
  WorkEvidenceReference,
  WorkTask,
  WorkTaskHistory,
} from "@/types/work-checklist";

export const workControl =
  "border-border-control bg-surface rounded-control min-h-10 w-full border px-3 py-2 text-sm";
const evidenceKey = (ref: WorkEvidenceReference) =>
  `${ref.kind}:${ref.id}:${ref.version}:${ref.generation}`;
/** Only routes owned by the matter workspace can be action targets. */
export function taskHref(matterId: string, task: WorkTask): string | null {
  const section = task.action?.section;
  if (
    task.action?.kind !== "navigate" ||
    !section ||
    !["documents", "facts", "checks", "drafts", "exports"].includes(section)
  )
    return null;
  const target =
    section === "checks" && task.action?.targetId
      ? `?requirement=${encodeURIComponent(task.action.targetId)}`
      : "";
  return `/matters/${encodeURIComponent(matterId)}/${section}${target}`;
}
function evidenceHref(matterId: string, ref: WorkEvidenceReference) {
  const kind = ref.kind.toLowerCase();
  const matterPath = `/matters/${encodeURIComponent(matterId)}`;
  if (kind === "document")
    return `${matterPath}/documents/${encodeURIComponent(ref.id)}/review`;
  if (kind === "form" || kind === "draft")
    return `${matterPath}/drafts/${encodeURIComponent(ref.id)}`;
  const section =
    kind.includes("document") || kind.includes("source")
      ? "documents"
      : kind.includes("fact") ||
          kind.includes("subject") ||
          kind.includes("transaction")
        ? "facts"
        : kind.includes("form") || kind.includes("draft")
          ? "drafts"
          : "checks";
  return `/matters/${encodeURIComponent(matterId)}/${section}`;
}
export function WorkEvidenceLinks({
  matterId,
  evidence,
}: {
  matterId: string;
  evidence: WorkEvidenceReference[];
}) {
  const t = useTranslations("workChecklist");
  return (
    <ul className="flex flex-wrap gap-x-4 gap-y-1 text-sm">
      {evidence.map((ref, index) => (
        <li key={`${ref.kind}:${ref.id}:${index}`}>
          <Link
            href={evidenceHref(matterId, ref)}
            className="text-teal inline-flex flex-wrap items-center gap-1 underline"
          >
            <FileText aria-hidden="true" className="size-4" />
            {t("evidence", { number: index + 1 })}
            {ref.version !== null
              ? ` · ${t("version", { version: ref.version })}`
              : ""}
            {ref.generation !== null
              ? ` · ${t("generation", { generation: ref.generation })}`
              : ""}
            {ref.associationVersion !== null
              ? ` · ${t("associationRevision", { version: ref.associationVersion })}`
              : ""}
          </Link>
        </li>
      ))}
    </ul>
  );
}

export function WorkTaskRow({
  task,
  matterId,
  getToken,
  title,
  reason,
  disabled,
  onDecision,
  active,
}: {
  task: WorkTask;
  matterId: string;
  getToken: TokenProvider;
  title: string;
  reason: string;
  disabled: boolean;
  active: boolean;
  onDecision: (
    task: WorkTask,
    decision: "complete" | "review" | "cancel",
    note: string,
    evidence?: WorkEvidenceReference[],
  ) => Promise<boolean>;
}) {
  const t = useTranslations("workChecklist");
  const id = useId();
  const details = useRef<HTMLDetailsElement | null>(null);
  const [history, setHistory] = useState<WorkTaskHistory | null>(null);
  const [historyBusy, setHistoryBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [note, setNote] = useState("");
  const [selectedEvidence, setSelectedEvidence] = useState<string[]>(() =>
    task.evidence.map(evidenceKey),
  );
  const [evidenceTouched, setEvidenceTouched] = useState(false);
  const [documentChoices, setDocumentChoices] = useState<
    { reference: WorkEvidenceReference; label: string }[]
  >([]);
  const [evidenceBusy, setEvidenceBusy] = useState(false);
  const historyRequests = useRef(0);
  const evidenceRequests = useRef(0);
  useEffect(
    () => () => {
      historyRequests.current++;
      evidenceRequests.current++;
    },
    [task.id, matterId],
  );
  useEffect(() => {
    if (active && details.current) {
      details.current.open = true;
      details.current.querySelector("summary")?.focus();
    }
  }, [active]);
  const historyLoad = async (cursor?: string) => {
    const current = ++historyRequests.current;
    setHistoryBusy(true);
    setError(null);
    try {
      const result = await getWorkTaskHistory(
        getToken,
        matterId,
        task.id,
        cursor,
      );
      if (current === historyRequests.current)
        setHistory((previous) =>
          cursor && previous
            ? { ...result, items: [...previous.items, ...result.items] }
            : result,
        );
    } catch (cause) {
      if (current === historyRequests.current)
        setError(apiErrorMessage(cause, t("historyUnavailable")));
    } finally {
      if (current === historyRequests.current) setHistoryBusy(false);
    }
  };
  const href = taskHref(matterId, task);
  const evidenceChoices = [
    ...task.evidence.map((reference, index) => ({
      reference,
      label: t("evidence", { number: index + 1 }),
    })),
    ...documentChoices.filter(
      ({ reference }) =>
        !task.evidence.some(
          (ref) => ref.kind === reference.kind && ref.id === reference.id,
        ),
    ),
  ];
  const loadEvidence = async () => {
    const current = ++evidenceRequests.current;
    setEvidenceBusy(true);
    setError(null);
    try {
      const inbox = await getCompleteDocumentInbox(getToken, matterId);
      if (current !== evidenceRequests.current) return;
      const common = {
        transactionId: null,
        subjectId: null,
        associationVersion: null,
      };
      setDocumentChoices([
        ...inbox.sourceFiles
          .filter((source) => !source.supersededBySourceFileId)
          .map((source) => ({
            reference: {
              kind: "source",
              id: source.id,
              version: source.version,
              generation: null,
              ...common,
            },
            label: source.originalFilename,
          })),
        ...inbox.documents
          .filter((document) => document.interpretationGeneration !== undefined)
          .map((document, index) => ({
            reference: {
              kind: "document",
              id: document.id,
              version: document.version,
              generation: document.interpretationGeneration ?? null,
              ...common,
            },
            label: `${t("documentNumber", { number: index + 1 })} · ${t("version", { version: document.version })}`,
          })),
      ]);
    } catch (cause) {
      if (current === evidenceRequests.current)
        setError(apiErrorMessage(cause, t("evidenceUnavailable")));
    } finally {
      if (current === evidenceRequests.current) setEvidenceBusy(false);
    }
  };
  const editable =
    task.origin === "lawyer" ||
    task.origin === "agent" ||
    (task.origin === "operational" && task.action?.kind === "decide");
  const Icon =
    task.state === "complete"
      ? CheckCircle2
      : task.state === "blocked" || task.state === "stale"
        ? AlertCircle
        : task.state === "in-progress" || task.state === "pending-applicability"
          ? Clock3
          : Circle;
  return (
    <div className="space-y-2 p-3">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="space-y-1">
          <p className="inline-flex items-center gap-2 font-medium">
            <Icon
              aria-hidden="true"
              className="size-4 shrink-0"
              strokeWidth={1.5}
            />
            <span>{title}</span>
          </p>
          <p className="text-muted-ink text-xs">{t(`states.${task.state}`)}</p>
        </div>
        {href && (
          <Link href={href} className={buttonClass("secondary", "sm")}>
            {t("review")}
          </Link>
        )}
        {editable && !["cancelled", "not-applicable"].includes(task.state) && (
          <Button
            size="sm"
            disabled={disabled}
            onClick={() => {
              if (details.current) details.current.open = true;
            }}
            aria-controls={`${id}-detail`}
          >
            {t(
              task.state === "complete"
                ? "reviewCompletion"
                : "recordCompletion",
            )}
          </Button>
        )}
      </div>
      <p className="text-muted-ink text-sm leading-6">{reason}</p>
      {task.evidence.length > 0 ? (
        <ul className="flex flex-wrap gap-x-4 gap-y-1 text-sm">
          {task.evidence.map((ref, index) => (
            <li key={`${ref.kind}:${ref.id}:${index}`}>
              <Link
                href={evidenceHref(matterId, ref)}
                className="text-teal inline-flex items-center gap-1 underline"
              >
                <FileText aria-hidden="true" className="size-4" />
                {t("evidence", { number: index + 1 })}
                {ref.version !== null
                  ? ` · ${t("version", { version: ref.version })}`
                  : ""}
              </Link>
            </li>
          ))}
        </ul>
      ) : (
        <p className="text-muted-ink text-xs">{t("noEvidence")}</p>
      )}
      <details ref={details} id={`${id}-detail`}>
        <summary className="text-muted-ink cursor-pointer text-xs">
          {t("details")}
        </summary>
        <div className="mt-3 space-y-3">
          <p className="text-muted-ink text-xs">
            {t(`origins.${task.origin}`)}
            {task.assignedTo
              ? ` · ${t("assigned", { actor: task.assignedTo })}`
              : ""}
          </p>
          {task.completedBy && (
            <p className="text-muted-ink text-sm">
              {t("completedBy", {
                actor: task.completedBy,
                time: task.completedAt ?? t("timeUnknown"),
              })}
            </p>
          )}
          {editable &&
            !["cancelled", "not-applicable"].includes(task.state) && (
              <div className="space-y-2">
                {task.origin === "operational" && (
                  <p className="text-muted-ink text-sm">
                    {t("operationalNotice")}
                  </p>
                )}
                <label className="block space-y-1 text-sm">
                  <span>{t("note")}</span>
                  <textarea
                    className={workControl}
                    value={note}
                    maxLength={4000}
                    disabled={disabled}
                    onChange={(event) => setNote(event.target.value)}
                  />
                </label>
                <Button
                  size="sm"
                  disabled={disabled || evidenceBusy}
                  onClick={() => void loadEvidence()}
                >
                  {t("linkEvidence")}
                </Button>
                {evidenceChoices.length > 0 && (
                  <fieldset className="space-y-2">
                    <legend className="text-sm">
                      {t("completionEvidence")}
                    </legend>
                    {evidenceChoices.map(({ reference: ref, label }) => (
                      <label
                        key={evidenceKey(ref)}
                        className="flex items-center gap-2 text-sm"
                      >
                        <input
                          type="checkbox"
                          disabled={disabled}
                          checked={selectedEvidence.includes(evidenceKey(ref))}
                          onChange={(event) => {
                            setEvidenceTouched(true);
                            setSelectedEvidence((values) =>
                              event.target.checked
                                ? [...values, evidenceKey(ref)]
                                : values.filter(
                                    (value) => value !== evidenceKey(ref),
                                  ),
                            );
                          }}
                        />
                        {label}
                      </label>
                    ))}
                  </fieldset>
                )}
                <div className="flex flex-wrap gap-2">
                  <Button
                    disabled={
                      disabled ||
                      (task.origin === "operational" &&
                        task.state !== "complete" &&
                        task.state !== "stale" &&
                        !note.trim() &&
                        selectedEvidence.length === 0)
                    }
                    onClick={() =>
                      void onDecision(
                        task,
                        task.state === "complete" || task.state === "stale"
                          ? "review"
                          : "complete",
                        note,
                        (task.state === "complete" || task.state === "stale") &&
                          !evidenceTouched
                          ? undefined
                          : evidenceChoices
                              .filter(({ reference }) =>
                                selectedEvidence.includes(
                                  evidenceKey(reference),
                                ),
                              )
                              .map(({ reference }) => reference),
                      )
                    }
                  >
                    {t(
                      task.state === "complete" || task.state === "stale"
                        ? "reviewCurrentEvidence"
                        : "completeTask",
                    )}
                  </Button>
                  {task.origin !== "operational" && (
                    <Button
                      disabled={disabled}
                      onClick={() => void onDecision(task, "cancel", note)}
                    >
                      {t("cancelTask")}
                    </Button>
                  )}
                </div>
              </div>
            )}
          {editable && (
            <Button
              size="sm"
              disabled={historyBusy}
              onClick={() => void historyLoad()}
            >
              {t("history")}
            </Button>
          )}
          {error && (
            <p role="alert" className="text-red text-sm">
              {error}
            </p>
          )}
          {history && (
            <div className="bg-canvas space-y-2 rounded p-3 text-sm">
              {history.items.length === 0 && <p>{t("noHistory")}</p>}
              {history.items.map((event) => (
                <div key={event.id}>
                  <p>
                    {t("historyEvent", {
                      actor: event.actorId,
                      time: event.createdAt,
                      decision: t.has(`decisions.${event.decision}`)
                        ? t(`decisions.${event.decision}`)
                        : t("recordedDecision"),
                    })}
                  </p>
                  {event.note && <p className="text-muted-ink">{event.note}</p>}
                  <WorkEvidenceLinks
                    matterId={matterId}
                    evidence={event.evidence ?? []}
                  />
                </div>
              ))}
              {history.nextCursor && (
                <Button
                  size="sm"
                  disabled={historyBusy}
                  onClick={() =>
                    void historyLoad(history.nextCursor ?? undefined)
                  }
                >
                  {t("moreHistory")}
                </Button>
              )}
            </div>
          )}
        </div>
      </details>
    </div>
  );
}
