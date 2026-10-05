"use client";

import {
  AlertCircle,
  Calendar,
  Download,
  File,
  LoaderCircle,
  Plus,
} from "lucide-react";
import { useFormatter, useTranslations } from "next-intl";
import { useCallback, useEffect, useState } from "react";
import { isApiEnabled, type TokenProvider, apiErrorMessage } from "@/lib/api/client";
import {
  createExport,
  createRegistrationEvent,
  listExports,
  listRegistrationEvents,
} from "@/lib/api/approvals";
import { listForms } from "@/lib/api/drafts";
import { getMatter } from "@/lib/api/matters";
import { useTokenProvider } from "@/lib/api/use-token-provider";
import { humanizeMessageKey } from "@/lib/i18n/humanize";
import type {
  ApiFormExportList,
  ApiRegistrationEventList,
  ApiRtaMatter,
  ExportFormat,
  RegistrationEventType,
} from "@/types/rta";
import { AppShell } from "@/components/shell/app-shell";
import { PageHeader } from "@/components/shell/page-header";
import { Button } from "@/components/ui/button";

export function ExportsScreen({ matterId }: { matterId: string }) {
  return isApiEnabled() ? (
    <ApiBoundExportsScreen matterId={matterId} />
  ) : (
    <DemoExportsScreen matterId={matterId} />
  );
}

function ApiBoundExportsScreen({ matterId }: { matterId: string }) {
  const getToken = useTokenProvider();
  return <ExportsScreenContent matterId={matterId} getToken={getToken} />;
}

function DemoExportsScreen({ matterId }: { matterId: string }) {
  return <DemoExportsContent matterId={matterId} />;
}

interface ExportsScreenContentProps {
  matterId: string;
  getToken: TokenProvider;
}

function ExportsScreenContent({ matterId, getToken }: ExportsScreenContentProps) {
  const t = useTranslations("exports");
  const tRoot = useTranslations();
  const format = useFormatter();
  const formatDate = (value: string) => format.dateTime(new Date(value), { dateStyle: "medium" });
  /** The watermark's own message, or a readable form of its key. */
  const watermarkText = (key: string) => (tRoot.has(key) ? tRoot(key) : humanizeMessageKey(key));
  /** Title of a generated form's template, or "Form 08" when it has no message. */
  const formTitle = (templateId: string) => {
    const key = `rta.form.${templateId.replace(/^rta\./, "").replace(/\./g, "_")}.title`;
    return tRoot.has(key) ? tRoot(key) : t("formFallback", { number: templateId.split(".").pop() ?? templateId });
  };

  const [matter, setMatter] = useState<ApiRtaMatter | null>(null);
  const [exportList, setExportList] = useState<ApiFormExportList | null>(null);
  const [eventList, setEventList] = useState<ApiRegistrationEventList | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Form for creating export
  const [showExportForm, setShowExportForm] = useState(false);
  const [availableForms, setAvailableForms] = useState<
    Array<{ id: string; templateId: string; formVersion: number }>
  >([]);
  const [selectedFormId, setSelectedFormId] = useState<string>("");
  const [selectedFormat, setSelectedFormat] = useState<ExportFormat>("WORKING_DRAFT_MANIFEST");
  const [creatingExport, setCreatingExport] = useState(false);

  // Form for registration event
  const [showEventForm, setShowEventForm] = useState(false);
  const [eventType, setEventType] = useState<RegistrationEventType>("ATTESTED");
  const [eventDate, setEventDate] = useState("");
  const [dayBookReference, setDayBookReference] = useState("");
  const [registryOffice, setRegistryOffice] = useState("");
  const [resultNote, setResultNote] = useState("");
  const [creatingEvent, setCreatingEvent] = useState(false);

  // Fetch all data
  const fetchData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [matterResult, exportsResult, eventsResult, formsResult] = await Promise.all([
        getMatter(getToken, matterId),
        listExports(getToken, matterId),
        listRegistrationEvents(getToken, matterId),
        listForms(getToken, matterId),
      ]);
      setMatter(matterResult);
      setExportList(exportsResult);
      setEventList(eventsResult);

      // Extract available forms
      const forms = formsResult.items.map((form) => ({
        id: form.id,
        templateId: form.templateId,
        formVersion: form.formVersion,
      }));
      setAvailableForms(forms);

      // Set default form if only one exists
      if (forms.length === 1) {
        setSelectedFormId(forms[0]!.id);
      }
    } catch (cause) {
      setError(apiErrorMessage(cause, t("loadError")));
    } finally {
      setLoading(false);
    }
  }, [getToken, matterId, t]);

  useEffect(() => {
    void fetchData();
  }, [fetchData]);

  // Handle create export
  const handleCreateExport = useCallback(async () => {
    if (!selectedFormId) {
      setError(t("formRequired"));
      return;
    }

    setCreatingExport(true);
    setError(null);
    try {
      const result = await createExport(getToken, selectedFormId, { format: selectedFormat });
      setExportList({
        items: [result, ...(exportList?.items ?? [])],
        page: exportList?.page ?? { nextCursor: null, hasMore: false, limit: 50 },
      });
      setShowExportForm(false);
      setSelectedFormId(availableForms.length === 1 ? availableForms[0]!.id : "");
      setSelectedFormat("WORKING_DRAFT_MANIFEST");
    } catch (cause) {
      setError(apiErrorMessage(cause, t("createError")));
    } finally {
      setCreatingExport(false);
    }
  }, [getToken, selectedFormId, selectedFormat, availableForms, exportList, t]);

  // Handle create registration event
  const handleCreateEvent = useCallback(async () => {
    if (!eventDate) {
      setError(t("eventDateRequired"));
      return;
    }

    setCreatingEvent(true);
    setError(null);
    try {
      const result = await createRegistrationEvent(getToken, matterId, {
        eventType,
        eventDate,
        ...(dayBookReference && { dayBookReference }),
        ...(registryOffice && { registryOffice }),
        ...(resultNote && { resultNote }),
      });

      setEventList({
        items: [result.event, ...(eventList?.items ?? [])],
        page: eventList?.page ?? { nextCursor: null, hasMore: false, limit: 50 },
      });

      setShowEventForm(false);
      setEventType("ATTESTED");
      setEventDate("");
      setDayBookReference("");
      setRegistryOffice("");
      setResultNote("");
    } catch (cause) {
      setError(apiErrorMessage(cause, t("createError")));
    } finally {
      setCreatingEvent(false);
    }
  }, [getToken, matterId, eventType, eventDate, dayBookReference, registryOffice, resultNote, eventList, t]);

  if (loading) {
    return (
      <AppShell matterId={matterId}>
        <div className="flex items-center gap-2 p-6 text-muted-ink">
          <LoaderCircle className="size-5 animate-spin" strokeWidth={1.5} aria-hidden="true" />
          {t("loading")}
        </div>
      </AppShell>
    );
  }

  if (!matter || !exportList || !eventList) {
    return (
      <AppShell matterId={matterId}>
        <div className="flex gap-3 rounded border border-red bg-red-bg p-6 text-sm text-red">
          <AlertCircle className="mt-0.5 size-5 shrink-0" strokeWidth={1.5} aria-hidden="true" />
          <p>{t("loadError")}</p>
        </div>
      </AppShell>
    );
  }

  const formatLabels: Record<ExportFormat, string> = {
    WORKING_DRAFT_MANIFEST: t("workingDraftManifest"),
    APPROVED_MANIFEST: t("approvedManifest"),
    EVIDENCE_SCHEDULE: t("evidenceSchedule"),
  };

  const formatDescriptions: Record<ExportFormat, string> = {
    WORKING_DRAFT_MANIFEST: t("workingDraftManifestDescription"),
    APPROVED_MANIFEST: t("approvedManifestDescription"),
    EVIDENCE_SCHEDULE: t("evidenceScheduleDescription"),
  };

  const eventTypeLabels: Record<RegistrationEventType, string> = {
    ATTESTED: t("attestedEvent"),
    PRESENTED: t("presentedEvent"),
    DAY_BOOK_ENTERED: t("dayBookEnteredEvent"),
    REGISTERED: t("registeredEvent"),
    REFUSED: t("refusedEvent"),
    RETURNED: t("returnedEvent"),
  };

  return (
    <AppShell matterId={matterId}>
      <PageHeader title={t("title")} description={t("description")} />

      {/* Warning banner */}
      <div className="border-amber bg-amber-bg border-b px-6 py-3">
        <div className="flex gap-3 text-sm text-amber-text">
          <AlertCircle className="size-5 shrink-0 mt-0.5" strokeWidth={1.5} aria-hidden="true" />
          <p>{t("warning")}</p>
        </div>
      </div>

      <div className="p-6">
        {/* Error message */}
        {error && (
          <div className="border-red bg-red-bg text-red mb-6 flex gap-3 rounded border p-4 text-sm">
            <AlertCircle className="mt-0.5 size-5 shrink-0" strokeWidth={1.5} aria-hidden="true" />
            <p>{error}</p>
          </div>
        )}

        {/* Exports section */}
        <section className="mb-8">
          <div className="mb-4 flex items-center justify-between">
            <div>
              <h2 className="text-lg font-semibold">{t("exportsSection")}</h2>
              <p className="text-muted-ink text-sm">{t("exportsDescription")}</p>
            </div>
            <Button
              variant="primary"
              onClick={() => setShowExportForm(!showExportForm)}
              disabled={creatingExport}
            >
              <Plus className="size-4" strokeWidth={1.5} />
              {t("createExport")}
            </Button>
          </div>

          {/* Create export form */}
          {showExportForm && (
            <div className="mb-6 rounded-card border border-border bg-surface p-4">
              <div className="space-y-4">
                <div>
                  <label className="block text-sm font-semibold">{t("selectForm")}</label>
                  <select
                    value={selectedFormId}
                    onChange={(e) => setSelectedFormId(e.target.value)}
                    className="border-border-control bg-surface mt-2 w-full rounded-control border px-3 py-2 text-sm"
                  >
                    <option value="">{t("chooseForm")}</option>
                    {availableForms.map((form) => (
                      <option key={form.id} value={form.id}>
                        {t("formOption", { title: formTitle(form.templateId), version: form.formVersion })}
                      </option>
                    ))}
                  </select>
                </div>

                <div>
                  <label className="block text-sm font-semibold">{t("selectFormat")}</label>
                  <div className="mt-2 space-y-2">
                    {(["WORKING_DRAFT_MANIFEST", "APPROVED_MANIFEST", "EVIDENCE_SCHEDULE"] as ExportFormat[]).map(
                      (format) => {
                        const inputId = `format-${format}`;
                        return (
                          <div key={format} className="flex items-start gap-3">
                            <input
                              id={inputId}
                              type="radio"
                              name="format"
                              value={format}
                              checked={selectedFormat === format}
                              onChange={(e) => setSelectedFormat(e.target.value as ExportFormat)}
                              className="mt-1"
                            />
                            <label htmlFor={inputId} className="flex-1 cursor-pointer">
                              <div className="font-medium text-sm">{formatLabels[format]}</div>
                              <div className="text-muted-ink text-xs">{formatDescriptions[format]}</div>
                            </label>
                          </div>
                        );
                      }
                    )}
                  </div>
                </div>

                <div className="flex gap-2 pt-2">
                  <Button
                    variant="primary"
                    disabled={!selectedFormId || creatingExport}
                    onClick={() => void handleCreateExport()}
                  >
                    {creatingExport ? (
                      <LoaderCircle className="size-4 animate-spin" strokeWidth={1.5} />
                    ) : (
                      <Download className="size-4" strokeWidth={1.5} />
                    )}
                    {creatingExport ? t("creating") : t("createExport")}
                  </Button>
                  <Button onClick={() => setShowExportForm(false)}>{t("cancel")}</Button>
                </div>
              </div>
            </div>
          )}

          {/* Exports list */}
          {exportList.items.length > 0 ? (
            <div className="space-y-2">
              {exportList.items.map((item) => (
                <div key={item.id} className="flex items-start gap-4 rounded-card border border-border bg-surface p-4 text-sm">
                  <File className="mt-0.5 size-5 shrink-0 text-muted-ink" strokeWidth={1.5} aria-hidden="true" />
                  <div className="flex-1">
                    <div className="font-semibold">{formatLabels[item.artifactKind] || item.artifactKind}</div>
                    <div className="text-muted-ink mt-1 text-xs">
                      {t("format")}: {formatLabels[item.artifactKind] || item.artifactKind}
                    </div>
                    <div className="text-muted-ink text-xs">
                      {t("createdAt")}: {formatDate(item.createdAt)}
                    </div>
                    {item.watermarked && (
                      <div className="text-amber-text text-xs">
                        {t("watermarked")}{item.watermarkKey ? `: ${watermarkText(item.watermarkKey)}` : ""}
                      </div>
                    )}
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div className="rounded-card border border-border bg-surface p-6 text-center text-sm">
              <File className="mx-auto mb-2 size-8 text-muted-ink" strokeWidth={1.5} aria-hidden="true" />
              <p className="text-muted-ink">{t("noExports")}</p>
            </div>
          )}
        </section>

        {/* Registration events section */}
        <section>
          <div className="mb-4 flex items-center justify-between">
            <div>
              <h2 className="text-lg font-semibold">{t("registrationSection")}</h2>
              <p className="text-muted-ink text-sm">{t("registrationDescription")}</p>
            </div>
            <Button
              variant="primary"
              onClick={() => setShowEventForm(!showEventForm)}
              disabled={creatingEvent}
            >
              <Plus className="size-4" strokeWidth={1.5} />
              {t("recordEvent")}
            </Button>
          </div>

          {/* Create event form */}
          {showEventForm && (
            <div className="mb-6 rounded-card border border-border bg-surface p-4">
              <div className="space-y-4">
                <div>
                  <label className="block text-sm font-semibold">{t("eventType")}</label>
                  <select
                    value={eventType}
                    onChange={(e) => setEventType(e.target.value as RegistrationEventType)}
                    className="border-border-control bg-surface mt-2 w-full rounded-control border px-3 py-2 text-sm"
                  >
                    {(["ATTESTED", "PRESENTED", "DAY_BOOK_ENTERED", "REGISTERED", "REFUSED"] as RegistrationEventType[]).map(
                      (type) => (
                        <option key={type} value={type}>
                          {eventTypeLabels[type]}
                        </option>
                      )
                    )}
                  </select>
                </div>

                <div>
                  <label className="block text-sm font-semibold">{t("eventDate")}</label>
                  <input
                    type="date"
                    value={eventDate}
                    onChange={(e) => setEventDate(e.target.value)}
                    className="border-border-control bg-surface mt-2 w-full rounded-control border px-3 py-2 text-sm"
                  />
                </div>

                <div>
                  <label className="block text-sm font-semibold">{t("dayBookReference")}</label>
                  <input
                    type="text"
                    value={dayBookReference}
                    onChange={(e) => setDayBookReference(e.target.value)}
                    placeholder={t("optional")}
                    className="border-border-control bg-surface mt-2 w-full rounded-control border px-3 py-2 text-sm"
                  />
                </div>

                <div>
                  <label className="block text-sm font-semibold">{t("registryOffice")}</label>
                  <input
                    type="text"
                    value={registryOffice}
                    onChange={(e) => setRegistryOffice(e.target.value)}
                    placeholder={t("optional")}
                    className="border-border-control bg-surface mt-2 w-full rounded-control border px-3 py-2 text-sm"
                  />
                </div>

                <div>
                  <label className="block text-sm font-semibold">{t("resultNote")}</label>
                  <textarea
                    value={resultNote}
                    onChange={(e) => setResultNote(e.target.value)}
                    placeholder={t("optional")}
                    className="border-border-control bg-surface mt-2 w-full rounded border px-3 py-2 text-sm"
                    rows={3}
                  />
                </div>

                <div className="flex gap-2 pt-2">
                  <Button
                    variant="primary"
                    disabled={!eventDate || creatingEvent}
                    onClick={() => void handleCreateEvent()}
                  >
                    {creatingEvent ? (
                      <LoaderCircle className="size-4 animate-spin" strokeWidth={1.5} />
                    ) : (
                      <Calendar className="size-4" strokeWidth={1.5} />
                    )}
                    {creatingEvent ? t("recording") : t("recordEventAction")}
                  </Button>
                  <Button onClick={() => setShowEventForm(false)}>{t("cancel")}</Button>
                </div>
              </div>
            </div>
          )}

          {/* Events list */}
          {eventList.items.length > 0 ? (
            <div className="space-y-2">
              {eventList.items.map((item) => (
                <div key={item.id} className="flex items-start gap-4 rounded-card border border-border bg-surface p-4 text-sm">
                  <Calendar className="mt-0.5 size-5 shrink-0 text-muted-ink" strokeWidth={1.5} aria-hidden="true" />
                  <div className="flex-1">
                    <div className="font-semibold">{eventTypeLabels[item.eventType]}</div>
                    <div className="text-muted-ink mt-1 text-xs">
                      {formatDate(item.eventDate)}
                    </div>
                    {item.dayBookReference && (
                      <div className="text-muted-ink text-xs">
                        {t("dayBookReference")}: {item.dayBookReference}
                      </div>
                    )}
                    {item.registryOffice && (
                      <div className="text-muted-ink text-xs">
                        {t("registryOffice")}: {item.registryOffice}
                      </div>
                    )}
                    {item.resultNote && (
                      <div className="text-muted-ink mt-2 text-xs">
                        {item.resultNote}
                      </div>
                    )}
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div className="rounded-card border border-border bg-surface p-6 text-center text-sm">
              <Calendar className="mx-auto mb-2 size-8 text-muted-ink" strokeWidth={1.5} aria-hidden="true" />
              <p className="text-muted-ink">{t("noEvents")}</p>
            </div>
          )}
        </section>
      </div>
    </AppShell>
  );
}

function DemoExportsContent({ matterId }: { matterId: string }) {
  const t = useTranslations("exports");
  return (
    <AppShell matterId={matterId}>
      <PageHeader title={t("title")} description={t("description")} />
      <div className="p-6">
        <div className="rounded-card border border-border bg-surface p-6">
          <p className="text-muted-ink text-sm">{t("demoUnavailable")}</p>
        </div>
      </div>
    </AppShell>
  );
}
