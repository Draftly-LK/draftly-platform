"use client";

import {
  ArrowLeft,
  ArrowRight,
  Building2,
  Check,
  FileKey2,
  Landmark,
  MapPinned,
  Upload,
} from "lucide-react";
import Image from "next/image";
import { motion, useReducedMotion } from "motion/react";
import { useTranslations } from "next-intl";
import { useRouter } from "next/navigation";
import { useMemo, useState } from "react";
import { hasAuthorizedDocumentCatalog } from "@/lib/documents/authorization";
import { classifyFileName } from "@/lib/documents/mock-pipeline";
import {
  queueDocumentFile,
  simulateDocumentProcessing,
  useDemoStore,
} from "@/lib/store";
import type { DocumentKind, DocumentRelation, MatterType } from "@/types";
import { LocaleToggle } from "@/components/shell/locale-toggle";
import { Button } from "@/components/ui/button";

const transactionTypes: MatterType[] = [
  "transfer",
  "gift",
  "lease",
  "mortgage",
  "other",
];

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

export function NewMatterScreen() {
  const t = useTranslations("newMatter");
  const td = useTranslations("documents");
  const router = useRouter();
  const reduceMotion = useReducedMotion();
  const createMatter = useDemoStore((state) => state.createMatter);
  const addDocument = useDemoStore((state) => state.addDocument);
  const [step, setStep] = useState(1);
  const [type, setType] = useState<MatterType>("transfer");
  const [reference, setReference] = useState("");
  const [clientReference, setClientReference] = useState("");
  const [files, setFiles] = useState<File[]>([]);
  const classifiedFiles = useMemo(
    () =>
      files.map((file) => ({
        file,
        result: classifyFileName(file.name, "rta", type),
      })),
    [files, type],
  );
  const finish = () => {
    const id = createMatter({
      reference: reference.trim() || t("matterPlaceholder"),
      clientReference: clientReference.trim() || undefined,
      regime: "rta",
      type,
    });
    const hasFiles = files.length > 0;
    files.forEach((file) => {
      const previewUrl = URL.createObjectURL(file);
      const hint = classifyFileName(file.name, "rta", type);
      const documentId = addDocument(file.name, {
        matterId: id,
        kind: "other",
        relation: "unclassified",
        identitySide: hint.identitySide,
        previewUrl,
      });
      queueDocumentFile(documentId, file);
      simulateDocumentProcessing(documentId);
    });
    router.push(
      hasFiles ? `/matters/${id}/documents?pair=1` : `/matters/${id}`,
    );
  };
  if (step === 1)
    return (
      <main className="bg-canvas min-h-screen">
        <header className="absolute inset-x-0 top-0 z-10 flex h-16 items-center px-6">
          <div className="font-heading text-ink text-3xl font-semibold">
            {t("entryTitle")}
          </div>
          <div className="ml-auto">
            <LocaleToggle />
          </div>
        </header>
        <section className="relative min-h-screen overflow-hidden pt-16">
          <Image
            src="/images/synthetic-notarial-worktable.png"
            alt={t("imageAlt")}
            fill
            priority
            sizes="100vw"
            className="object-cover object-center"
          />
          <div className="relative z-[1] flex min-h-[calc(100vh-64px)] flex-col">
            <div className="flex flex-1 items-center px-6 py-10 sm:px-12 lg:px-20">
              <motion.div
                initial={reduceMotion ? false : { opacity: 0 }}
                animate={{ opacity: 1 }}
                transition={{ duration: 0.25 }}
                className="max-w-xl"
              >
                <div className="text-forest text-sm font-semibold uppercase">
                  {t("entryEyebrow")}
                </div>
                <h1 className="mt-2 text-6xl font-semibold sm:text-7xl">
                  {t("entryTitle")}
                </h1>
                <p className="text-ink mt-4 max-w-lg text-lg leading-8">
                  {t("entryBody")}
                </p>
              </motion.div>
            </div>
            <div className="border-border-strong bg-surface/95 border-t px-6 py-5 sm:px-12 lg:px-20">
              <div className="flex flex-wrap items-end gap-4">
                <div className="min-w-0 flex-1">
                  <h2 className="text-2xl font-semibold">
                    {t("chooseRegime")}
                  </h2>
                  <div className="mt-3 grid gap-2 sm:grid-cols-4">
                    <RegimeChoice
                      active
                      icon={<FileKey2 strokeWidth={1.5} />}
                      title={t("rta")}
                      status={t("available")}
                    />
                    <RegimeChoice
                      icon={<Landmark strokeWidth={1.5} />}
                      title={t("rdo")}
                      status={t("future")}
                    />
                    <RegimeChoice
                      icon={<Building2 strokeWidth={1.5} />}
                      title={t("apartment")}
                      status={t("future")}
                    />
                    <RegimeChoice
                      icon={<MapPinned strokeWidth={1.5} />}
                      title={t("special")}
                      status={t("future")}
                    />
                  </div>
                </div>
                <Button variant="primary" onClick={() => setStep(2)}>
                  {t("continue")}
                  <ArrowRight className="size-4" strokeWidth={1.5} />
                </Button>
              </div>
            </div>
          </div>
        </section>
      </main>
    );
  return (
    <main className="bg-canvas min-h-screen">
      <header className="border-border bg-surface flex h-16 items-center border-b px-6">
        <div className="font-heading text-2xl font-semibold">
          {t("entryTitle")}
        </div>
        <div className="ml-auto">
          <LocaleToggle />
        </div>
      </header>
      <div className="mx-auto max-w-2xl p-6 sm:p-10">
        <div className="text-muted-ink text-xs font-semibold uppercase">
          {t("step", { current: step })}
        </div>
        {step === 2 && (
          <section className="mt-3">
            <h1 className="text-4xl font-semibold">{t("typeTitle")}</h1>
            <p className="text-muted-ink mt-2">{t("typeBody")}</p>
            <div className="mt-6 grid gap-2 sm:grid-cols-2">
              {transactionTypes.map((item) => (
                <button
                  key={item}
                  className={`flex min-h-14 items-center justify-between rounded border p-4 text-left font-medium ${type === item ? "border-forest bg-selected-bg text-forest" : "border-border-strong bg-surface hover:bg-hover-bg"}`}
                  onClick={() => setType(item)}
                >
                  {t(item)}
                  {type === item && (
                    <Check className="size-5" strokeWidth={1.5} />
                  )}
                </button>
              ))}
            </div>
          </section>
        )}
        {step === 3 && (
          <section className="mt-3">
            <h1 className="text-4xl font-semibold">{t("referenceTitle")}</h1>
            <p className="text-muted-ink mt-2">{t("referenceBody")}</p>
            <label className="mt-6 block font-medium">
              {t("matterReference")}
              <input
                className="border-border-strong bg-surface mt-1 h-11 w-full rounded border px-3"
                value={reference}
                placeholder={t("matterPlaceholder")}
                onChange={(event) => setReference(event.target.value)}
              />
            </label>
            <label className="mt-4 block font-medium">
              {t("clientReference")}
              <input
                className="border-border-strong bg-surface mt-1 h-11 w-full rounded border px-3"
                value={clientReference}
                placeholder={t("clientPlaceholder")}
                onChange={(event) => setClientReference(event.target.value)}
              />
            </label>
            <div className="border-amber bg-amber-bg text-amber-text mt-4 border-l-2 p-3 text-sm">
              {t("privacy")}
            </div>
          </section>
        )}
        {step === 4 && (
          <section className="mt-3">
            <h1 className="text-4xl font-semibold">{t("documentsTitle")}</h1>
            <p className="text-muted-ink mt-2">{t("documentsBody")}</p>
            <p className="text-muted-ink mt-3 text-sm">
              {hasAuthorizedDocumentCatalog("rta", type)
                ? t("authorizedHintTransfer")
                : t("authorizedHintEmpty")}
            </p>
            <label className="border-border-strong bg-surface hover:bg-hover-bg mt-6 flex min-h-40 cursor-pointer flex-col items-center justify-center rounded border border-dashed p-6 text-center">
              <Upload className="text-forest size-6" strokeWidth={1.5} />
              <span className="mt-2 font-medium">{t("chooseDocuments")}</span>
              <span className="text-muted-ink mt-1 text-sm">
                {t("selectedFiles", { count: files.length })}
              </span>
              <input
                className="sr-only"
                type="file"
                multiple
                accept="application/pdf,image/*"
                onChange={(event) =>
                  setFiles(Array.from(event.target.files ?? []))
                }
              />
            </label>
            {classifiedFiles.length > 0 && (
              <ul className="divide-border border-border mt-4 divide-y border-y">
                {classifiedFiles.map(({ file, result }) => (
                  <li
                    key={file.name}
                    className="flex flex-wrap items-center justify-between gap-2 py-2 text-sm"
                  >
                    <span>{file.name}</span>
                    <span className="text-muted-ink">
                      {t("detectedAs", {
                        name: file.name,
                        kind: td(kindKeys[result.kind]),
                        relation: td(relationKeys[result.relation]),
                      })}
                    </span>
                  </li>
                ))}
              </ul>
            )}
          </section>
        )}
        <footer className="border-border mt-8 flex gap-2 border-t pt-4">
          <Button onClick={() => setStep((value) => Math.max(1, value - 1))}>
            <ArrowLeft className="size-4" strokeWidth={1.5} />
            {t("back")}
          </Button>
          {step < 4 ? (
            <Button
              className="ml-auto"
              variant="primary"
              onClick={() => setStep((value) => value + 1)}
            >
              {t("continue")}
              <ArrowRight className="size-4" strokeWidth={1.5} />
            </Button>
          ) : (
            <Button className="ml-auto" variant="primary" onClick={finish}>
              {t("create")}
              <ArrowRight className="size-4" strokeWidth={1.5} />
            </Button>
          )}
        </footer>
      </div>
    </main>
  );
}

function RegimeChoice({
  icon,
  title,
  status,
  active = false,
}: {
  icon: React.ReactNode;
  title: string;
  status: string;
  active?: boolean;
}) {
  return (
    <button
      disabled={!active}
      aria-pressed={active}
      className={`flex min-h-20 items-center gap-3 rounded border p-3 text-left ${active ? "border-forest bg-soft-green" : "border-border bg-disabled-bg text-disabled-fg"}`}
    >
      <span className="[&_svg]:size-5 [&_svg]:stroke-[1.5]">{icon}</span>
      <span>
        <span className="block font-semibold">{title}</span>
        <span className="block text-xs">{status}</span>
      </span>
    </button>
  );
}
