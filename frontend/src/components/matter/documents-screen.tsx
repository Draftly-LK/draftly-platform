"use client";

import {
  AlertTriangle,
  Check,
  CircleHelp,
  Edit3,
  FileCheck2,
  FileImage,
  History,
  Layers,
  RefreshCw,
  Replace,
  Tag,
  Upload,
} from "lucide-react";
import { useTranslations } from "next-intl";
import { useEffect, useMemo, useState } from "react";
import { hasAuthorizedDocumentCatalog } from "@/lib/documents/authorization";
import {
  buildDocumentDisplayRows,
  combinedProcessingState,
  type IdentityFieldSources,
} from "@/lib/documents/identity-groups";
import type { IdentityPairAssignment } from "@/lib/documents/mock-pipeline";
import { classifyFileName } from "@/lib/documents/mock-pipeline";
import {
  simulateDocumentProcessing,
  queueDocumentFile,
  useDemoStore,
} from "@/lib/store";
import type {
  DocumentKind,
  DocumentRelation,
  IdentityExtractedFields,
  MatterDocument,
} from "@/types";
import { IDENTITY_FIELD_KEYS } from "@/types/document";
import { AppShell } from "@/components/shell/app-shell";
import { PageHeader } from "@/components/shell/page-header";
import { Button } from "@/components/ui/button";
import { StatusBadge } from "@/components/ui/status-badge";
import { ExtractionEditor } from "./extraction-editor-shell";
import { IdentityPairingDialog } from "./identity-pairing-dialog";

const kindKeys: Record<
  DocumentKind,
  | "kindDeed"
  | "kindPlan"
  | "kindIdentity"
  | "kindAssessment"
  | "kindRegistry"
  | "kindAt"
  | "kindOther"
> = {
  deed: "kindDeed",
  "survey-plan": "kindPlan",
  identity: "kindIdentity",
  assessment: "kindAssessment",
  "registry-extract": "kindRegistry",
  "at-form": "kindAt",
  other: "kindOther",
};

const relationKeys: Record<
  DocumentRelation,
  "relationAuthorized" | "relationUnrelated" | "relationUnclassified"
> = {
  authorized: "relationAuthorized",
  unrelated: "relationUnrelated",
  unclassified: "relationUnclassified",
};

function RelationBadge({
  relation,
  label,
}: {
  relation: DocumentRelation;
  label: string;
}) {
  const Icon =
    relation === "authorized"
      ? FileCheck2
      : relation === "unrelated"
        ? AlertTriangle
        : CircleHelp;
  const styles =
    relation === "authorized"
      ? "border-forest bg-soft-green text-forest"
      : relation === "unrelated"
        ? "border-amber bg-amber-bg text-amber-text"
        : "border-border-strong bg-surface text-ink";
  return (
    <span
      className={`inline-flex min-h-7 items-center gap-1.5 rounded-full border px-2 py-1 text-xs font-semibold ${styles}`}
    >
      <Icon aria-hidden="true" className="size-4" strokeWidth={1.5} />
      {label}
    </span>
  );
}

function hasCompleteIdentityPair(documents: MatterDocument[]): boolean {
  const groups = new Map<string, { front: boolean; back: boolean }>();
  for (const document of documents) {
    if (document.kind !== "identity" || !document.identityGroupId) continue;
    const entry = groups.get(document.identityGroupId) ?? {
      front: false,
      back: false,
    };
    if (document.identitySide === "front") entry.front = true;
    if (document.identitySide === "back") entry.back = true;
    groups.set(document.identityGroupId, entry);
  }
  return [...groups.values()].some((entry) => entry.front && entry.back);
}

function IdentityFieldsEditor({
  fields,
  sources,
  editable,
  onSave,
}: {
  fields: IdentityExtractedFields;
  sources?: IdentityFieldSources;
  editable: boolean;
  onSave: (fields: IdentityExtractedFields) => void;
}) {
  const t = useTranslations("documents");
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState<IdentityExtractedFields>(fields);

  useEffect(() => {
    setDraft(fields);
    setEditing(false);
  }, [fields]);

  const labels: Record<keyof IdentityExtractedFields, string> = {
    nicNumber: t("fieldNicNumber"),
    nameSi: t("fieldNameSi"),
    nameEn: t("fieldNameEn"),
    sex: t("fieldSex"),
    dateOfBirth: t("fieldDateOfBirth"),
    addressEn: t("fieldAddressEn"),
    serialNumber: t("fieldSerialNumber"),
    dateOfIssue: t("fieldDateOfIssue"),
    placeOfBirthEn: t("fieldPlaceOfBirthEn"),
  };

  return (
    <>
      <div className="flex items-center justify-between gap-3">
        <h2 className="text-xl font-semibold">{t("extracted")}</h2>
        {editable && !editing && (
          <Button
            type="button"
            variant="secondary"
            className="min-h-8 px-2 text-xs"
            onClick={() => setEditing(true)}
          >
            <Edit3 className="size-4" strokeWidth={1.5} />
            {t("editAttributes")}
          </Button>
        )}
      </div>
      <div className="mt-3 space-y-3">
        {IDENTITY_FIELD_KEYS.map((key) => {
          const value = draft[key];
          const source = sources?.[key];
          return (
            <label key={key} className="block">
              <span className="flex items-center justify-between gap-2 text-sm font-medium">
                {labels[key]}
                {source && source !== "unknown" && (
                  <span className="text-muted-ink text-xs font-normal">
                    {source === "front" ? t("fromFront") : t("fromBack")}
                  </span>
                )}
              </span>
              {editing ? (
                <input
                  value={value ?? ""}
                  onChange={(event) =>
                    setDraft((current) => ({
                      ...current,
                      [key]: event.target.value.trimStart() || null,
                    }))
                  }
                  placeholder={t("undetected")}
                  className="border-border-strong focus-visible:ring-teal bg-surface mt-1 min-h-10 w-full rounded border px-3 text-sm outline-none focus-visible:ring-2"
                />
              ) : (
                <div
                  className={`border-border bg-canvas mt-1 min-h-10 rounded border px-3 py-2 text-sm ${value ? "" : "text-muted-ink italic"}`}
                >
                  {value ?? t("undetected")}
                </div>
              )}
            </label>
          );
        })}
      </div>
      {editing && (
        <div className="mt-4 flex justify-end gap-2">
          <Button
            type="button"
            variant="secondary"
            onClick={() => {
              setDraft(fields);
              setEditing(false);
            }}
          >
            {t("cancelAttributeEdit")}
          </Button>
          <Button
            type="button"
            onClick={() => {
              const normalized = Object.fromEntries(
                IDENTITY_FIELD_KEYS.map((key) => [
                  key,
                  draft[key]?.trim() || null,
                ]),
              ) as unknown as IdentityExtractedFields;
              onSave(normalized);
              setEditing(false);
            }}
          >
            <Check className="size-4" strokeWidth={1.5} />
            {t("saveAttributes")}
          </Button>
        </div>
      )}
    </>
  );
}

export function DocumentsScreen({
  matterId,
  openPairing = false,
}: {
  matterId: string;
  openPairing?: boolean;
}) {
  const t = useTranslations("documents");
  const tf = useTranslations("facts");
  const allDocuments = useDemoStore((state) => state.documents);
  const allFacts = useDemoStore((state) => state.facts);
  const matters = useDemoStore((state) => state.matters);
  const addDocument = useDemoStore((state) => state.addDocument);
  const retryDocument = useDemoStore((state) => state.retryDocument);
  const replaceDocument = useDemoStore((state) => state.replaceDocument);
  const resolveCheck = useDemoStore((state) => state.resolveCheck);
  const assignDocumentKind = useDemoStore((state) => state.assignDocumentKind);
  const setIdentityPairing = useDemoStore((state) => state.setIdentityPairing);
  const updateDocumentExtraction = useDemoStore(
    (state) => state.updateDocumentExtraction,
  );
  const updateIdentityFields = useDemoStore(
    (state) => state.updateIdentityFields,
  );
  const matter = matters.find((item) => item.id === matterId);
  const documents = allDocuments.filter(
    (document) => document.matterId === matterId,
  );
  const facts = allFacts.filter((fact) => fact.matterId === matterId);
  const displayRows = useMemo(
    () => buildDocumentDisplayRows(documents),
    [documents],
  );
  const [selectedId, setSelectedId] = useState(documents[0]?.id);
  const [announcement, setAnnouncement] = useState("");
  const [pairingOpen, setPairingOpen] = useState(false);
  const selectedRow =
    displayRows.find((row) =>
      row.members.some((document) => document.id === selectedId),
    ) ?? displayRows[0];
  const selected =
    selectedRow?.members.find((document) => document.id === selectedId) ??
    selectedRow?.primary;
  const identityDocs = useMemo(
    () => documents.filter((document) => document.kind === "identity"),
    [documents],
  );
  const processingBusy = documents.some(
    (document) => document.processingState === "extracting",
  );
  const readyFronts = identityDocs.filter(
    (document) =>
      document.processingState === "ready-for-review" &&
      document.identitySide === "front",
  );
  const readyBacks = identityDocs.filter(
    (document) =>
      document.processingState === "ready-for-review" &&
      document.identitySide === "back",
  );
  const canAutoOpenPairing =
    openPairing &&
    !processingBusy &&
    readyFronts.length > 0 &&
    readyBacks.length > 0;
  const needsIdentityPair =
    matter?.regime === "rta" &&
    matter.type === "transfer" &&
    !hasCompleteIdentityPair(documents);
  const authorizedCatalog = matter
    ? hasAuthorizedDocumentCatalog(matter.regime, matter.type)
    : false;

  const upload = (file: File | undefined) => {
    if (!file) return;
    const previewUrl = URL.createObjectURL(file);
    const hint =
      matter != null
        ? classifyFileName(file.name, matter.regime, matter.type)
        : null;
    const id = addDocument(file.name, {
      matterId,
      kind: "other",
      relation: "unclassified",
      identitySide: hint?.identitySide,
      previewUrl,
    });
    queueDocumentFile(id, file);
    setSelectedId(id);
    setAnnouncement(t("uploadReady", { name: file.name }));
    simulateDocumentProcessing(id);
  };
  const retry = (id: string) => {
    retryDocument(id);
    simulateDocumentProcessing(id);
  };
  const replace = (id: string) => {
    replaceDocument(id, t("replacementFileName"), t("replacementReason"));
    simulateDocumentProcessing(id);
  };
  const confirmPairing = (assignments: IdentityPairAssignment[]) => {
    setIdentityPairing(assignments);
    setPairingOpen(false);
    setAnnouncement(t("pairingConfirm"));
  };
  const sideLabel = (document: MatterDocument) => {
    if (document.kind !== "identity") return "—";
    if (document.identitySide === "front") return t("sideFront");
    if (document.identitySide === "back") return t("sideBack");
    return t("sideUnknown");
  };
  const rowName = (row: (typeof displayRows)[number]) => {
    const nameEn = row.mergedFields?.nameEn;
    if (nameEn) return t("identityCardFor", { name: nameEn });
    return row.primary.displayName ?? row.primary.fileName;
  };
  const rowSide = (row: (typeof displayRows)[number]) => {
    if (row.front && row.back) return t("sideFrontAndBack");
    return sideLabel(row.primary);
  };

  // Open pairing only after intake finishes and both sides exist
  useEffect(() => {
    if (canAutoOpenPairing) setPairingOpen(true);
  }, [canAutoOpenPairing]);

  return (
    <AppShell matterId={matterId}>
      <PageHeader
        title={t("title")}
        description={t("description")}
        action={
          <div className="flex flex-wrap items-center gap-2">
            {identityDocs.length > 0 && (
              <Button type="button" onClick={() => setPairingOpen(true)}>
                <Layers className="size-4" strokeWidth={1.5} />
                {t("pairIdentity")}
              </Button>
            )}
            <label className="border-forest bg-forest inline-flex min-h-10 cursor-pointer items-center gap-2 rounded border px-3 py-2 font-medium text-white">
              <Upload className="size-4" strokeWidth={1.5} />
              {t("upload")}
              <input
                className="sr-only"
                type="file"
                accept="application/pdf,image/*"
                onChange={(event) => upload(event.target.files?.[0])}
              />
            </label>
          </div>
        }
      />
      <div aria-live="polite" className="sr-only">
        {announcement}
      </div>
      <div className="p-6">
        <p className="text-muted-ink mb-4 text-sm">
          {authorizedCatalog
            ? t("authorizedHintTransfer")
            : t("authorizedHintEmpty")}
        </p>
        <section className="border-border-strong bg-surface overflow-hidden rounded border">
          <div className="overflow-x-auto">
            <table className="w-full min-w-[1300px] border-collapse whitespace-nowrap text-left">
              <thead className="bg-canvas text-muted-ink sticky top-0 z-10 text-xs">
                <tr className="border-border h-10 border-b">
                  <th className="px-3">{t("file")}</th>
                  <th className="px-3">{t("type")}</th>
                  <th className="px-3">{t("relation")}</th>
                  <th className="px-3">{t("side")}</th>
                  <th className="px-3">{t("language")}</th>
                  <th className="px-3">{t("pages")}</th>
                  <th className="px-3">{t("confidence")}</th>
                  <th className="px-3">{t("quality")}</th>
                  <th className="px-3">{t("state")}</th>
                  <th className="px-3">{t("actions")}</th>
                </tr>
              </thead>
              <tbody>
                {displayRows.map((row) => {
                  const document = row.primary;
                  const confidences = row.members
                    .map((member) => member.extractionConfidence)
                    .filter(
                      (confidence): confidence is number =>
                        confidence !== undefined,
                    );
                  const confidence =
                    confidences.length > 0
                      ? confidences.reduce((sum, value) => sum + value, 0) /
                        confidences.length
                      : undefined;
                  const processingState = combinedProcessingState(row.members);
                  const qualityCount = row.members.reduce(
                    (count, member) => count + member.qualityProblems.length,
                    0,
                  );
                  return (
                    <tr
                      key={row.id}
                      className={`border-border h-11 border-b last:border-b-0 ${selectedRow?.id === row.id ? "border-l-forest bg-selected-bg border-l-2" : "hover:bg-hover-bg"}`}
                    >
                      <td className="max-w-60 truncate px-3 font-medium">
                        <button
                          className="hover:text-teal text-left"
                          onClick={() => setSelectedId(document.id)}
                        >
                          {rowName(row)}
                        </button>
                        {row.front && row.back && (
                          <span className="border-border-strong text-muted-ink ml-2 rounded-full border px-2 py-0.5 text-xs">
                            {t("oneDocumentTwoSides")}
                          </span>
                        )}
                        {document.kind === "at-form" && (
                          <span className="border-border-strong text-muted-ink ml-2 rounded-full border px-2 py-0.5 text-xs">
                            {t("unsupported")}
                          </span>
                        )}
                      </td>
                      <td className="px-3 text-sm">
                        {t(kindKeys[document.kind])}
                      </td>
                      <td className="px-3">
                        <RelationBadge
                          relation={document.relation}
                          label={t(relationKeys[document.relation])}
                        />
                      </td>
                      <td className="px-3 text-sm">{rowSide(row)}</td>
                      <td className="px-3 uppercase">{document.language}</td>
                      <td className="px-3 tabular-nums">
                        {row.members.reduce(
                          (count, member) => count + member.pageCount,
                          0,
                        )}
                      </td>
                      <td className="px-3 tabular-nums">
                        {confidence === undefined
                          ? "—"
                          : `${Math.round(confidence * 100)}%`}
                      </td>
                      <td className="px-3 text-sm">
                        {qualityCount ? (
                          <span className="text-amber-text">
                            {t("qualityIssue", {
                              count: qualityCount,
                            })}
                          </span>
                        ) : (
                          <span className="text-muted-ink">
                            {t("noIssues")}
                          </span>
                        )}
                      </td>
                      <td className="px-3">
                        <StatusBadge status={processingState} />
                      </td>
                      <td className="px-3">
                        <div className="flex items-center gap-1">
                          {document.relation === "unclassified" &&
                            authorizedCatalog && (
                              <button
                                aria-label={t("assignIdentity")}
                                title={t("assignIdentity")}
                                className="hover:bg-active-bg grid size-8 place-items-center rounded"
                                onClick={() => {
                                  assignDocumentKind(document.id, "identity");
                                  useDemoStore
                                    .getState()
                                    .completeDocumentExtraction(document.id);
                                  setPairingOpen(true);
                                }}
                              >
                                <Tag className="size-4" strokeWidth={1.5} />
                              </button>
                            )}
                          {processingState === "failed" && (
                            <button
                              aria-label={t("retry")}
                              title={t("retry")}
                              className="hover:bg-active-bg grid size-8 place-items-center rounded"
                              onClick={() => retry(document.id)}
                            >
                              <RefreshCw className="size-4" strokeWidth={1.5} />
                            </button>
                          )}
                          <button
                            aria-label={t("replace")}
                            title={t("replace")}
                            className="hover:bg-active-bg grid size-8 place-items-center rounded"
                            onClick={() => replace(document.id)}
                          >
                            <Replace className="size-4" strokeWidth={1.5} />
                          </button>
                          <button
                            className="border-border-strong hover:bg-hover-bg min-h-8 rounded border px-2 text-xs"
                            onClick={() => setSelectedId(document.id)}
                          >
                            {t("open")}
                          </button>
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </section>
        {selected && (
          <section
            aria-label={t("review", {
              name: selectedRow ? rowName(selectedRow) : selected.fileName,
            })}
            className="border-border-strong bg-surface mt-6 grid overflow-hidden rounded border xl:grid-cols-[180px_minmax(320px,1fr)_340px]"
          >
            <aside className="border-border border-b p-3 xl:border-b-0 xl:border-r">
              <h2 className="text-sm font-semibold">
                {selectedRow?.primary.kind === "identity"
                  ? t("identitySides")
                  : t("pageThumbs")}
              </h2>
              <div className="mt-3 flex gap-2 overflow-x-auto xl:block xl:space-y-2">
                {selectedRow?.primary.kind === "identity"
                  ? selectedRow.members.map((member) => (
                      <button
                        key={member.id}
                        type="button"
                        onClick={() => setSelectedId(member.id)}
                        className={`border-border-strong hover:border-forest w-24 shrink-0 rounded border p-2 text-xs xl:w-full ${
                          selected.id === member.id
                            ? "border-forest bg-selected-bg"
                            : "bg-canvas"
                        }`}
                        aria-pressed={selected.id === member.id}
                      >
                        {member.previewUrl ? (
                          // eslint-disable-next-line @next/next/no-img-element
                          <img
                            src={member.previewUrl}
                            alt=""
                            className="mb-2 aspect-[3/2] w-full object-contain"
                          />
                        ) : (
                          <FileImage
                            className="mx-auto mb-2 size-5"
                            strokeWidth={1.5}
                          />
                        )}
                        {sideLabel(member)}
                      </button>
                    ))
                  : Array.from({ length: selected.pageCount }, (_, index) => (
                      <button
                        key={index}
                        className="border-border-strong bg-canvas hover:border-forest grid aspect-[3/4] w-20 shrink-0 place-items-center rounded border text-xs xl:w-full"
                        aria-label={t("page", { page: index + 1 })}
                      >
                        <FileImage className="size-5" strokeWidth={1.5} />
                        {t("page", { page: index + 1 })}
                      </button>
                    ))}
              </div>
              {selectedRow?.front && selectedRow.back && (
                <div className="border-forest bg-soft-green text-forest mt-3 flex items-center gap-2 rounded border p-2 text-xs font-medium">
                  <FileCheck2 className="size-4" strokeWidth={1.5} />
                  {t("pairComplete")}
                </div>
              )}
            </aside>
            <div className="border-border bg-canvas min-h-[360px] border-b p-6 xl:border-b-0 xl:border-r">
              {selected.previewUrl && (
                // eslint-disable-next-line @next/next/no-img-element
                <img
                  src={selected.previewUrl}
                  alt={selected.displayName ?? selected.fileName}
                  className="border-border-strong mb-4 max-h-64 w-full rounded border object-contain"
                />
              )}
              {selected.extractedText !== undefined ? (
                selected.extractedText.trim() ? (
                  <ExtractionEditor
                    documentId={selected.id}
                    text={selected.extractedText}
                    editable={selected.processingState === "ready-for-review"}
                    onSave={(text) => {
                      updateDocumentExtraction(
                        selected.id,
                        text,
                        selected.extractedFields,
                      );
                      setAnnouncement(t("extractionSaved"));
                    }}
                  />
                ) : (
                  <div className="border-border-strong bg-surface mx-auto flex min-h-[200px] max-w-lg flex-col border p-8">
                    <div className="font-heading text-2xl font-semibold">
                      {t("extractionPreview")}
                    </div>
                    <p className="text-muted-ink mt-3">{t("noTextDetected")}</p>
                  </div>
                )
              ) : (
                <div className="border-border-strong bg-surface mx-auto flex min-h-[320px] max-w-lg flex-col border p-8">
                  <div className="font-heading text-2xl font-semibold">
                    {t("evidence")}
                  </div>
                  <p className="text-muted-ink mt-3">{t("evidenceBody")}</p>
                  <div className="border-teal bg-teal-bg mt-8 border-l-2 p-3 text-sm">
                    {facts.find(
                      (fact) => fact.evidence?.documentId === selected.id,
                    )?.evidence?.snippet ?? t("evidenceBody")}
                  </div>
                </div>
              )}
            </div>
            <aside className="p-4">
              {selected.kind === "identity" && selectedRow?.mergedFields ? (
                <IdentityFieldsEditor
                  fields={selectedRow.mergedFields}
                  sources={selectedRow.fieldSources}
                  editable={selectedRow.members.every(
                    (member) => member.processingState === "ready-for-review",
                  )}
                  onSave={(fields) => {
                    if (selected.identityGroupId) {
                      updateIdentityFields(selected.identityGroupId, fields);
                    } else {
                      updateDocumentExtraction(
                        selected.id,
                        selected.extractedText ?? "",
                        fields,
                      );
                    }
                    setAnnouncement(t("attributesSaved"));
                  }}
                />
              ) : (
                <>
                  <h2 className="text-xl font-semibold">{t("extracted")}</h2>
                  <div className="divide-border border-border mt-3 divide-y border-y">
                    {selected.kind !== "identity" &&
                      selected.extractedFields &&
                      Object.entries(selected.extractedFields).map(
                        ([key, value]) => (
                          <div key={key} className="py-3">
                            <div className="font-medium capitalize">
                              {key.replace(/([A-Z])/g, " $1")}
                            </div>
                            <div
                              className={`mt-1 text-sm ${value ? "" : "text-muted-ink italic"}`}
                            >
                              {value ?? t("undetected")}
                            </div>
                          </div>
                        ),
                      )}
                  </div>
                </>
              )}
              <div className="divide-border border-border mt-3 divide-y border-y">
                {facts
                  .filter((fact) => fact.evidence?.documentId === selected.id)
                  .map((fact) => (
                    <div key={fact.id} className="py-3">
                      <div className="flex items-center justify-between gap-2">
                        <span className="font-medium">
                          {tf(
                            fact.labelKey.split(".").at(-1) as
                              | "deedNumber"
                              | "transferor"
                              | "transferee"
                              | "extent"
                              | "assessmentNumber",
                          )}
                        </span>
                        <StatusBadge status={fact.verificationState} />
                      </div>
                      <div className="mt-1 text-sm">
                        {String(fact.value ?? "—")}
                      </div>
                      <div className="text-teal mt-1 text-xs">
                        {t("source", { page: fact.evidence?.page ?? 1 })}
                      </div>
                    </div>
                  ))}
              </div>
              <details className="border-border-strong mt-4 rounded border p-3">
                <summary className="flex cursor-pointer items-center gap-2 font-medium">
                  <History className="size-4" strokeWidth={1.5} />
                  {t("versionHistory")}
                </summary>
                <div className="text-muted-ink mt-2 space-y-2 text-sm">
                  {selected.versions.map((version) => (
                    <div key={version.id}>
                      {version.fileName} ·{" "}
                      {version.reason || t("initialVersion")}
                    </div>
                  ))}
                </div>
              </details>
              {selected.processingState === "failed" && (
                <div className="mt-4 grid gap-2">
                  <Button onClick={() => retry(selected.id)}>
                    <RefreshCw className="size-4" strokeWidth={1.5} />
                    {t("retry")}
                  </Button>
                  <Button onClick={() => replace(selected.id)}>
                    <Replace className="size-4" strokeWidth={1.5} />
                    {t("replace")}
                  </Button>
                  <Button onClick={() => setAnnouncement(t("manualReady"))}>
                    {t("manual")}
                  </Button>
                </div>
              )}
            </aside>
          </section>
        )}
        {needsIdentityPair && (
          <section className="border-border bg-surface mt-6 border-y px-4 py-5">
            <h2 className="text-xl font-semibold">
              {t("missingRecommendations")}
            </h2>
            <p className="text-muted-ink mt-1">{t("missingBody")}</p>
            <Button
              className="mt-3"
              onClick={() => {
                resolveCheck(
                  "check-registry",
                  "document-requested",
                  t("requestReady"),
                );
                setAnnouncement(t("requestReady"));
              }}
            >
              {t("requestDocument")}
            </Button>
          </section>
        )}
      </div>
      <IdentityPairingDialog
        documents={identityDocs}
        open={pairingOpen && identityDocs.length > 0}
        onClose={() => setPairingOpen(false)}
        onConfirm={confirmPairing}
      />
    </AppShell>
  );
}
