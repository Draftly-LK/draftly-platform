"use client";

import {
  AlertTriangle,
  Check,
  CircleCheck,
  LoaderCircle,
  RefreshCw,
} from "lucide-react";
import { useTranslations } from "next-intl";
import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { apiErrorMessage, type TokenProvider } from "@/lib/api/client";
import {
  getDetectedDocument,
  recordBoundaryDecision,
  recordClassificationDecision,
  refreshDocumentExtraction,
} from "@/lib/api/documents";
import { getRtaDocumentClasses, type ApiRtaDocumentClass } from "@/lib/api/rta";
import { humanizeMessageKey } from "@/lib/i18n/humanize";
import type { ApiDetectedDocument } from "@/types/rta";

/** Confirmed by the lawyer: nothing left to decide about what the document is or which pages it spans. */
export function isDocumentDecided(document: ApiDetectedDocument): boolean {
  return (
    document.classStatus === "LAWYER_CONFIRMED" &&
    document.boundaryStatus === "CONFIRMED" &&
    document.extractionState === "current" &&
    document.versionRelationship !== "SUPERSEDED"
  );
}

/**
 * The two lawyer decisions every detected document needs: what it is, and
 * which pages it spans. Shared by the full review (page images and fields)
 * and the classification-only fallback, so both finish the same way.
 */
export function DocumentDecisions({
  getToken,
  matterId,
  documentId,
  onChange,
}: {
  getToken: TokenProvider;
  matterId: string;
  documentId: string;
  /** Called with the document after it loads and after every decision. */
  onChange?: (document: ApiDetectedDocument) => void;
}) {
  const t = useTranslations("classificationReview");
  const tRoot = useTranslations();
  const textFor = (key: string, fallbackId: string) =>
    tRoot.has(key)
      ? tRoot(key)
      : humanizeMessageKey(fallbackId.split(".").pop() ?? fallbackId);
  const [document, setDocument] = useState<ApiDetectedDocument | null>(null);
  const [classes, setClasses] = useState<ApiRtaDocumentClass[]>([]);
  const [selected, setSelected] = useState("");
  const [saving, setSaving] = useState<"class" | "boundary" | "refresh" | null>(
    null,
  );
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    Promise.all([
      getDetectedDocument(getToken, documentId),
      getRtaDocumentClasses(getToken),
    ])
      .then(([found, contract]) => {
        if (!active) return;
        if (found.id !== documentId || found.matterId !== matterId) {
          setError(t("documentNotFound"));
          return;
        }
        setDocument(found);
        setClasses(contract.classes);
        setSelected(found.classId ?? "");
        onChange?.(found);
      })
      .catch((cause: unknown) => {
        if (active) setError(apiErrorMessage(cause, t("error")));
      });
    return () => {
      active = false;
    };
    // `onChange` is a notification, not an input: re-running on a new callback would refetch for nothing.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [documentId, getToken, matterId, t]);

  async function decide(kind: "class" | "boundary" | "refresh") {
    if (!document) return;
    setSaving(kind);
    setError(null);
    try {
      const updated =
        kind === "refresh"
          ? await refreshDocumentExtraction(
              getToken,
              documentId,
              document.version,
            )
          : kind === "class"
            ? await recordClassificationDecision(
                getToken,
                documentId,
                { classId: selected },
                document.version,
              )
            : await recordBoundaryDecision(
                getToken,
                documentId,
                {
                  fragments: document.fragments.map((fragment) => ({
                    sourceFileId: fragment.sourceFileId,
                    pageStart: fragment.pageStart,
                    pageEnd: fragment.pageEnd,
                    orderInDocument: fragment.orderInDocument,
                  })),
                },
                document.version,
              );
      setDocument(updated);
      onChange?.(updated);
    } catch (cause: unknown) {
      setError(apiErrorMessage(cause, t("error")));
    } finally {
      setSaving(null);
    }
  }

  if (!document) {
    return (
      <section className="border-border bg-surface rounded-card border p-4">
        {error ? (
          <p role="alert" className="text-red text-sm">
            {error}
          </p>
        ) : (
          <LoaderCircle
            aria-label={t("loading")}
            className="size-5 animate-spin"
            strokeWidth={1.5}
          />
        )}
      </section>
    );
  }

  const classConfirmed =
    document.classStatus === "LAWYER_CONFIRMED" &&
    selected === document.classId;
  const boundaryConfirmed = document.boundaryStatus === "CONFIRMED";
  const pages = document.fragments
    .map((fragment) =>
      t("pageRange", { start: fragment.pageStart, end: fragment.pageEnd }),
    )
    .join(", ");

  return (
    <section className="border-border bg-surface rounded-card space-y-4 border p-4">
      <h2 className="font-semibold">{t("decisionsTitle")}</h2>
      {error ? (
        <p role="alert" className="text-red text-sm">
          {error}
        </p>
      ) : null}
      <div
        role="status"
        className="border-border rounded-control border p-3 text-sm"
      >
        <p className="flex items-start gap-2">
          {document.extractionState === "current" ? (
            <CircleCheck className="size-4 shrink-0" aria-hidden="true" />
          ) : (
            <AlertTriangle className="size-4 shrink-0" aria-hidden="true" />
          )}
          {t(`extraction.${document.extractionState ?? "unavailable"}`)}
        </p>
        {document.extractionState !== "current" &&
          classConfirmed &&
          boundaryConfirmed &&
          document.versionRelationship !== "SUPERSEDED" && (
            <Button
              size="sm"
              className="mt-3"
              disabled={saving !== null}
              onClick={() => void decide("refresh")}
            >
              <RefreshCw className="size-4" aria-hidden="true" />
              {t("refreshExtraction")}
            </Button>
          )}
      </div>

      <div className="space-y-2">
        <label className="block text-sm font-medium">
          {t("selectClass")}
          <select
            value={selected}
            onChange={(event) => setSelected(event.target.value)}
            disabled={saving !== null}
            className="border-border-control bg-surface rounded-control mt-1 min-h-10 w-full border px-3 py-2"
          >
            <option value="">{t("chooseClass")}</option>
            {classes.map((item) => (
              <option key={item.id} value={item.id}>
                {textFor(item.labelKey, item.id)}
              </option>
            ))}
          </select>
        </label>
        {classConfirmed ? (
          <p className="text-teal flex items-center gap-1.5 text-sm">
            <CircleCheck
              aria-hidden="true"
              className="size-4"
              strokeWidth={1.5}
            />
            {t("classConfirmed")}
          </p>
        ) : (
          <Button
            size="sm"
            disabled={!selected || saving !== null}
            onClick={() => void decide("class")}
          >
            {saving === "class" ? (
              <LoaderCircle
                aria-hidden="true"
                className="size-4 animate-spin"
                strokeWidth={1.5}
              />
            ) : (
              <Check aria-hidden="true" className="size-4" strokeWidth={1.5} />
            )}
            {t("confirmClassification")}
          </Button>
        )}
      </div>

      <div className="border-border space-y-2 border-t pt-4">
        <p className="text-sm font-medium">{t("pagesLabel")}</p>
        <p className="text-muted-ink text-sm">{pages}</p>
        {boundaryConfirmed ? (
          <p className="text-teal flex items-center gap-1.5 text-sm">
            <CircleCheck
              aria-hidden="true"
              className="size-4"
              strokeWidth={1.5}
            />
            {t("boundaryConfirmed")}
          </p>
        ) : (
          <Button
            size="sm"
            disabled={saving !== null}
            onClick={() => void decide("boundary")}
          >
            {saving === "boundary" ? (
              <LoaderCircle
                aria-hidden="true"
                className="size-4 animate-spin"
                strokeWidth={1.5}
              />
            ) : (
              <Check aria-hidden="true" className="size-4" strokeWidth={1.5} />
            )}
            {t("confirmBoundaryNow")}
          </Button>
        )}
      </div>
    </section>
  );
}
