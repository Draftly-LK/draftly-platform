"use client";

import { Clock3 } from "lucide-react";
import { useTranslations } from "next-intl";
import { useDemoStore } from "@/lib/store";

export function ActivityTimeline({ matterId }: { matterId?: string }) {
  const t = useTranslations("activity");
  const actionT = useTranslations("activity.actions");
  const targetT = useTranslations("activity.targets");
  const allEvents = useDemoStore((state) => state.auditEvents);
  const events = (
    matterId
      ? allEvents.filter((event) => event.matterId === matterId)
      : allEvents
  ).toReversed();
  if (!events.length)
    return <p className="text-muted-ink p-6">{t("noEvents")}</p>;
  return (
    <ol className="border-border-strong relative border-l">
      {events.map((event) => (
        <li
          key={event.id}
          className="border-border relative ml-6 border-b py-4 last:border-b-0"
        >
          <span className="border-forest bg-soft-green absolute -left-[33px] top-5 grid size-4 place-items-center rounded-full border">
            <Clock3 className="text-forest size-2.5" strokeWidth={1.5} />
          </span>
          <div className="flex flex-wrap items-start justify-between gap-2">
            <div>
              <div className="font-medium">
                {t("event", { action: actionT(actionKey(event.action)) })}
              </div>
              <div className="text-muted-ink mt-1 text-xs">
                {t("actor", { actor: event.actor })} ·{" "}
                {t("target", {
                  type: targetT(targetKey(event.targetType)),
                  id: event.targetId,
                })}
              </div>
            </div>
            <div className="text-muted-ink text-xs tabular-nums">
              {t("timestamp", formatColomboTimestamp(event.timestamp))}
            </div>
          </div>
          <span className="border-border-strong mt-2 inline-block rounded-full border px-2 py-1 text-xs">
            {event.id.startsWith("audit-live")
              ? t("liveSession")
              : t("historical")}
          </span>
        </li>
      ))}
    </ol>
  );
}

const actionKeys = {
  "matter.created": "matterCreated",
  "document.uploaded": "documentUploaded",
  "document.extracting": "documentExtracting",
  "document.ready-for-review": "documentReady",
  "document.failed": "documentFailed",
  "document.replaced": "documentReplaced",
  "document.retry-requested": "documentRetryRequested",
  "source-file.processing-not-configured": "sourceFileProcessingNotConfigured",
  "fact.verified": "factVerified",
  "fact.corrected": "factCorrected",
  "fact.added-manually": "factAddedManually",
  "check.resolved": "checkResolved",
  "check.waived": "checkWaived",
  "check.document-requested": "checkDocumentRequested",
  "check.checklist-created": "checklistCreated",
  "workflow.step-overridden": "workflowStepOverridden",
  "workflow.step-completed": "workflowStepCompleted",
  "draft.created": "draftCreated",
  "draft.version-created": "draftVersionCreated",
  "draft.version-restored": "draftVersionRestored",
  "draft.approved": "draftApproved",
  "draft.exported-docx": "draftExportedDocx",
  "draft.exported-pdf": "draftExportedPdf",
  "assistant.added-to-matter": "assistantAddedToMatter",
  "assistant.saved-to-library": "assistantSavedToLibrary",
  "assistant.check-created": "assistantCheckCreated",
  "assistant.authority-review-requested": "authorityReviewRequested",
  "assistant.question-asked": "assistantQuestionAsked",
  "demo.reset": "demoReset",
} as const;

type ActionKey = (typeof actionKeys)[keyof typeof actionKeys] | "updated";

function actionKey(action: string): ActionKey {
  return actionKeys[action as keyof typeof actionKeys] ?? "updated";
}

const targetKeys = {
  matter: "matter",
  document: "document",
  fact: "fact",
  check: "check",
  "workflow-step": "workflowStep",
  draft: "draft",
  answer: "answer",
  permission: "permission",
} as const;

function targetKey(target: keyof typeof targetKeys) {
  return targetKeys[target];
}

function formatColomboTimestamp(timestamp: string) {
  const colombo = new Date(new Date(timestamp).getTime() + 330 * 60 * 1000)
    .toISOString()
    .slice(0, 16);
  const [date = "", time = ""] = colombo.split("T");
  return { date, time };
}
