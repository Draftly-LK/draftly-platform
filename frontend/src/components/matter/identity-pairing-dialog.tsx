"use client";

import { GripVertical, Plus, X } from "lucide-react";
import { useTranslations } from "next-intl";
import { useEffect, useMemo, useState } from "react";
import {
  nextIdentityGroupId,
  personForIdentityGroup,
  type IdentityPairAssignment,
} from "@/lib/documents/mock-pipeline";
import type { IdentitySide, MatterDocument } from "@/types";
import { Button } from "@/components/ui/button";

type PersonSlot = {
  groupId: string;
  frontId?: string;
  backId?: string;
};

type DragPayload = {
  documentId: string;
};

function buildInitialSlots(documents: MatterDocument[]): PersonSlot[] {
  const groups = new Map<string, PersonSlot>();
  const ungrouped: MatterDocument[] = [];
  for (const document of documents) {
    if (document.identityGroupId) {
      const existing = groups.get(document.identityGroupId) ?? {
        groupId: document.identityGroupId,
      };
      if (document.identitySide === "front") existing.frontId = document.id;
      else if (document.identitySide === "back") existing.backId = document.id;
      else if (!existing.frontId) existing.frontId = document.id;
      else existing.backId = document.id;
      groups.set(document.identityGroupId, existing);
    } else {
      ungrouped.push(document);
    }
  }
  const slots = [...groups.values()];
  for (const document of ungrouped) {
    const empty = slots.find((slot) => !slot.frontId || !slot.backId);
    if (empty) {
      if (!empty.frontId) empty.frontId = document.id;
      else empty.backId = document.id;
    } else {
      slots.push({
        groupId: nextIdentityGroupId(slots.map((slot) => slot.groupId)),
        frontId: document.id,
      });
    }
  }
  if (slots.length === 0) {
    return [{ groupId: "identity-group-1" }];
  }
  return slots;
}

function DropSlot({
  label,
  document,
  onDropDocument,
  onClear,
}: {
  label: string;
  document?: MatterDocument;
  onDropDocument: (documentId: string) => void;
  onClear: () => void;
}) {
  const t = useTranslations("documents");
  return (
    <div
      className="border-border-strong bg-canvas min-h-24 rounded border border-dashed p-3"
      onDragOver={(event) => {
        event.preventDefault();
        event.dataTransfer.dropEffect = "move";
      }}
      onDrop={(event) => {
        event.preventDefault();
        const raw = event.dataTransfer.getData("application/json");
        if (!raw) return;
        const payload = JSON.parse(raw) as DragPayload;
        onDropDocument(payload.documentId);
      }}
    >
      <div className="text-muted-ink text-xs font-semibold uppercase tracking-wide">
        {label}
      </div>
      {document ? (
        <div className="border-border-strong bg-surface mt-2 flex items-start gap-2 rounded border p-2">
          <GripVertical
            className="text-muted-ink mt-0.5 size-4 shrink-0"
            strokeWidth={1.5}
          />
          <div className="min-w-0 flex-1">
            <div className="truncate text-sm font-medium">
              {document.displayName ?? document.fileName}
            </div>
            <div className="text-muted-ink truncate text-xs">
              {document.fileName}
            </div>
          </div>
          <button
            type="button"
            className="hover:bg-active-bg grid size-7 place-items-center rounded"
            aria-label={t("pairingClear")}
            onClick={onClear}
          >
            <X className="size-4" strokeWidth={1.5} />
          </button>
        </div>
      ) : (
        <p className="text-muted-ink mt-3 text-sm">{t("pairingDropHint")}</p>
      )}
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
  const [slots, setSlots] = useState<PersonSlot[]>(() =>
    buildInitialSlots(identityDocs),
  );

  useEffect(() => {
    if (open) setSlots(buildInitialSlots(identityDocs));
  }, [open, identityDocs]);

  const assignedIds = new Set(
    slots.flatMap((slot) => [slot.frontId, slot.backId].filter(Boolean)),
  );
  const pool = identityDocs.filter((document) => !assignedIds.has(document.id));

  if (!open) return null;

  const place = (
    groupId: string,
    side: IdentitySide,
    documentId: string,
  ) => {
    setSlots((current) => {
      const cleared = current.map((slot) => ({
        ...slot,
        frontId: slot.frontId === documentId ? undefined : slot.frontId,
        backId: slot.backId === documentId ? undefined : slot.backId,
      }));
      return cleared.map((slot) => {
        if (slot.groupId !== groupId) return slot;
        if (side === "front") return { ...slot, frontId: documentId };
        return { ...slot, backId: documentId };
      });
    });
  };

  const confirm = () => {
    const assignments: IdentityPairAssignment[] = [];
    for (const slot of slots) {
      if (slot.frontId) {
        assignments.push({
          documentId: slot.frontId,
          identityGroupId: slot.groupId,
          identitySide: "front",
        });
      }
      if (slot.backId) {
        assignments.push({
          documentId: slot.backId,
          identityGroupId: slot.groupId,
          identitySide: "back",
        });
      }
    }
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
        className="border-border-strong bg-surface relative z-10 max-h-[90vh] w-full max-w-3xl overflow-y-auto rounded-lg border shadow-none"
      >
        <div className="border-border flex items-start justify-between gap-4 border-b px-5 py-4">
          <div>
            <h2
              id="identity-pairing-title"
              className="font-heading text-2xl font-semibold"
            >
              {t("pairingTitle")}
            </h2>
            <p className="text-muted-ink mt-1 text-sm">{t("pairingBody")}</p>
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
          {pool.length > 0 && (
            <section>
              <h3 className="text-sm font-semibold">{t("pairingPool")}</h3>
              <div className="mt-2 flex flex-wrap gap-2">
                {pool.map((document) => (
                  <div
                    key={document.id}
                    draggable
                    onDragStart={(event) => {
                      event.dataTransfer.setData(
                        "application/json",
                        JSON.stringify({ documentId: document.id }),
                      );
                      event.dataTransfer.effectAllowed = "move";
                    }}
                    className="border-border-strong bg-canvas flex cursor-grab items-center gap-2 rounded border px-3 py-2 active:cursor-grabbing"
                  >
                    <GripVertical className="size-4" strokeWidth={1.5} />
                    <span className="text-sm">
                      {document.displayName ?? document.fileName}
                    </span>
                  </div>
                ))}
              </div>
            </section>
          )}
          {slots.map((slot, index) => (
            <section
              key={slot.groupId}
              className="border-border-strong rounded border p-4"
            >
              <h3 className="font-medium">
                {t("pairingPerson", {
                  index: index + 1,
                  name: personForIdentityGroup(slot.groupId),
                })}
              </h3>
              <div className="mt-3 grid gap-3 sm:grid-cols-2">
                <DropSlot
                  label={t("sideFront")}
                  document={identityDocs.find(
                    (document) => document.id === slot.frontId,
                  )}
                  onDropDocument={(documentId) =>
                    place(slot.groupId, "front", documentId)
                  }
                  onClear={() =>
                    setSlots((current) =>
                      current.map((item) =>
                        item.groupId === slot.groupId
                          ? { ...item, frontId: undefined }
                          : item,
                      ),
                    )
                  }
                />
                <DropSlot
                  label={t("sideBack")}
                  document={identityDocs.find(
                    (document) => document.id === slot.backId,
                  )}
                  onDropDocument={(documentId) =>
                    place(slot.groupId, "back", documentId)
                  }
                  onClear={() =>
                    setSlots((current) =>
                      current.map((item) =>
                        item.groupId === slot.groupId
                          ? { ...item, backId: undefined }
                          : item,
                      ),
                    )
                  }
                />
              </div>
            </section>
          ))}
          <Button
            type="button"
            variant="secondary"
            onClick={() =>
              setSlots((current) => [
                ...current,
                {
                  groupId: nextIdentityGroupId(
                    current.map((slot) => slot.groupId),
                  ),
                },
              ])
            }
          >
            <Plus className="size-4" strokeWidth={1.5} />
            {t("pairingAddPerson")}
          </Button>
        </div>
        <div className="border-border flex justify-end gap-2 border-t px-5 py-4">
          <Button type="button" variant="secondary" onClick={onClose}>
            {t("pairingCancel")}
          </Button>
          <Button type="button" onClick={confirm}>
            {t("pairingConfirm")}
          </Button>
        </div>
      </div>
    </div>
  );
}
