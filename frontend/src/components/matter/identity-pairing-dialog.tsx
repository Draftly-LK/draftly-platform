"use client";

import { GripVertical, X } from "lucide-react";
import { useTranslations } from "next-intl";
import { useEffect, useMemo, useState } from "react";
import {
  nextIdentityGroupId,
  type IdentityPairAssignment,
} from "@/lib/documents/mock-pipeline";
import type { MatterDocument } from "@/types";
import { Button } from "@/components/ui/button";

type DragPayload = { documentId: string };

type PairStep = {
  frontId: string;
  backId?: string;
};

function Preview({ document }: { document: MatterDocument }) {
  if (document.previewUrl) {
    return (
      // eslint-disable-next-line @next/next/no-img-element
      <img
        src={document.previewUrl}
        alt={document.displayName ?? document.fileName}
        className="border-border-strong bg-canvas h-28 w-full rounded border object-contain"
      />
    );
  }
  return (
    <div className="border-border-strong bg-canvas text-muted-ink flex h-28 items-center justify-center rounded border text-xs">
      {document.fileName}
    </div>
  );
}

export function IdentityPairingDialog({
  documents,
  open,
  onClose,
  onConfirm,
}: {
  documents: MatterDocument[];
  open: boolean;
  onClose: () => void;
  onConfirm: (assignments: IdentityPairAssignment[]) => void;
}) {
  const t = useTranslations("documents");
  const identityDocs = useMemo(
    () => documents.filter((document) => document.kind === "identity"),
    [documents],
  );

  const fronts = useMemo(() => {
    const explicit = identityDocs.filter(
      (document) => document.identitySide === "front",
    );
    if (explicit.length > 0) return explicit;
    return identityDocs.filter(
      (document) =>
        document.identitySide === "unknown" || !document.identitySide,
    );
  }, [identityDocs]);
  const backs = useMemo(
    () => identityDocs.filter((document) => document.identitySide === "back"),
    [identityDocs],
  );

  const [stepIndex, setStepIndex] = useState(0);
  const [pairs, setPairs] = useState<PairStep[]>([]);
  const [currentBackId, setCurrentBackId] = useState<string | undefined>();

  useEffect(() => {
    if (!open) return;
    setStepIndex(0);
    setPairs(fronts.map((front) => ({ frontId: front.id })));
    setCurrentBackId(undefined);
  }, [open, fronts]);

  const matchedBackIds = new Set(
    pairs.map((pair) => pair.backId).filter(Boolean),
  );
  const unmatchedBacks = backs.filter(
    (document) =>
      !matchedBackIds.has(document.id) || document.id === currentBackId,
  );
  const currentFront = fronts[stepIndex];
  const isLast = stepIndex >= fronts.length - 1;

  if (!open) return null;

  const advance = () => {
    const nextPairs = pairs.map((pair, index) =>
      index === stepIndex ? { ...pair, backId: currentBackId } : pair,
    );
    setPairs(nextPairs);
    if (!isLast) {
      setStepIndex((value) => value + 1);
      setCurrentBackId(nextPairs[stepIndex + 1]?.backId);
      return;
    }
    const assignments: IdentityPairAssignment[] = [];
    const usedGroups: string[] = [];
    nextPairs.forEach((pair) => {
      const groupId = nextIdentityGroupId(usedGroups);
      usedGroups.push(groupId);
      assignments.push({
        documentId: pair.frontId,
        identityGroupId: groupId,
        identitySide: "front",
      });
      if (pair.backId) {
        assignments.push({
          documentId: pair.backId,
          identityGroupId: groupId,
          identitySide: "back",
        });
      }
    });
    onConfirm(assignments);
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      <button
        type="button"
        className="absolute inset-0 bg-black/40"
        aria-label={t("pairingClose")}
        onClick={onClose}
      />
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="identity-pairing-title"
        className="border-border-strong bg-surface relative z-10 max-h-[90vh] w-full max-w-3xl overflow-y-auto rounded-lg border"
      >
        <div className="border-border flex items-start justify-between gap-4 border-b px-5 py-4">
          <div>
            <h2
              id="identity-pairing-title"
              className="font-heading text-2xl font-semibold"
            >
              {t("pairingTitle")}
            </h2>
            <p className="text-muted-ink mt-1 text-sm">
              {t("pairingBodySequential")}
            </p>
            {fronts.length > 0 && (
              <p className="text-muted-ink mt-2 text-xs font-semibold uppercase">
                {t("pairingStep", {
                  current: stepIndex + 1,
                  total: fronts.length,
                })}
              </p>
            )}
          </div>
          <button
            type="button"
            className="hover:bg-active-bg grid size-9 place-items-center rounded"
            aria-label={t("pairingClose")}
            onClick={onClose}
          >
            <X className="size-5" strokeWidth={1.5} />
          </button>
        </div>

        <div className="space-y-4 p-5">
          {!currentFront && (
            <p className="text-muted-ink text-sm">{t("pairingNoFronts")}</p>
          )}
          {currentFront && (
            <>
              <section className="border-border-strong rounded border p-4">
                <h3 className="text-sm font-semibold uppercase tracking-wide">
                  {t("sideFront")}
                </h3>
                <div className="mt-3">
                  <Preview document={currentFront} />
                  <div className="mt-2 text-sm font-medium">
                    {currentFront.displayName ?? currentFront.fileName}
                  </div>
                </div>
                <div
                  className="border-border-strong bg-canvas mt-4 min-h-24 rounded border border-dashed p-3"
                  onDragOver={(event) => {
                    event.preventDefault();
                    event.dataTransfer.dropEffect = "move";
                  }}
                  onDrop={(event) => {
                    event.preventDefault();
                    const raw = event.dataTransfer.getData("application/json");
                    if (!raw) return;
                    const payload = JSON.parse(raw) as DragPayload;
                    setCurrentBackId(payload.documentId);
                  }}
                >
                  <div className="text-muted-ink text-xs font-semibold uppercase">
                    {t("sideBack")}
                  </div>
                  {currentBackId ? (
                    <div className="mt-2 flex items-start gap-2">
                      <div className="min-w-0 flex-1">
                        <Preview
                          document={
                            identityDocs.find(
                              (document) => document.id === currentBackId,
                            ) ?? currentFront
                          }
                        />
                      </div>
                      <button
                        type="button"
                        className="hover:bg-active-bg grid size-7 place-items-center rounded"
                        aria-label={t("pairingClear")}
                        onClick={() => setCurrentBackId(undefined)}
                      >
                        <X className="size-4" strokeWidth={1.5} />
                      </button>
                    </div>
                  ) : (
                    <p className="text-muted-ink mt-3 text-sm">
                      {t("pairingDropBackHint")}
                    </p>
                  )}
                </div>
              </section>

              <section>
                <h3 className="text-sm font-semibold">
                  {t("pairingBackPool")}
                </h3>
                <div className="mt-2 grid gap-2 sm:grid-cols-2">
                  {unmatchedBacks.map((document) => (
                    <button
                      type="button"
                      key={document.id}
                      draggable
                      aria-pressed={currentBackId === document.id}
                      onClick={() => setCurrentBackId(document.id)}
                      onDragStart={(event) => {
                        event.dataTransfer.setData(
                          "application/json",
                          JSON.stringify({ documentId: document.id }),
                        );
                        event.dataTransfer.effectAllowed = "move";
                      }}
                      className={`border-border-strong bg-canvas cursor-grab rounded border p-2 text-left active:cursor-grabbing ${
                        currentBackId === document.id
                          ? "border-forest bg-selected-bg"
                          : "hover:border-forest"
                      }`}
                    >
                      <div className="mb-2 flex items-center gap-1 text-xs font-medium">
                        <GripVertical className="size-4" strokeWidth={1.5} />
                        {document.displayName ?? document.fileName}
                      </div>
                      <Preview document={document} />
                      <div className="text-teal mt-2 text-xs font-medium">
                        {currentBackId === document.id
                          ? t("pairingSelectedBack")
                          : t("pairingSelectBack")}
                      </div>
                    </button>
                  ))}
                  {unmatchedBacks.length === 0 && (
                    <p className="text-muted-ink text-sm">
                      {t("pairingNoBacks")}
                    </p>
                  )}
                </div>
              </section>
            </>
          )}
        </div>

        <div className="border-border flex justify-end gap-2 border-t px-5 py-4">
          <Button type="button" variant="secondary" onClick={onClose}>
            {t("pairingCancel")}
          </Button>
          <Button
            type="button"
            disabled={!currentFront || !currentBackId}
            onClick={advance}
          >
            {isLast ? t("pairingConfirm") : t("pairingNextFront")}
          </Button>
        </div>
      </div>
    </div>
  );
}
