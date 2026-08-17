"use client";

/**
 * New Matter — the seven-step RTA intake flow (§4.1, §4.2, §11.1).
 *
 * Three rules govern this screen and none of them are cosmetic:
 *
 * 1. `UNKNOWN` is a real answer. It is offered as a first-class choice on every
 *    tri-state question and is never coerced into `NO` on the way to the server
 *    (§4.1, §4.4).
 * 2. The checklist compiler is server-owned. When the backend is not configured
 *    the screen says so instead of inventing a checklist, because two compilers
 *    would be two sources of truth (§5.1).
 * 3. Choosing a family is not choosing an instrument, and neither is a guess by
 *    this component. The exact subtype is confirmed by the responsible lawyer
 *    through `POST /matters/{id}/subtype` (§3.5, §12.4).
 */

import {
  AlertCircle,
  ArrowLeft,
  ArrowRight,
  Building2,
  Check,
  CircleDashed,
  CircleHelp,
  FileKey2,
  FlaskConical,
  Gavel,
  Landmark,
  LoaderCircle,
  MapPinned,
  Scale,
  ScrollText,
  ShieldCheck,
  Upload,
  UserCog,
  Wrench,
} from "lucide-react";
import Image from "next/image";
import { motion, useReducedMotion } from "motion/react";
import { useTranslations } from "next-intl";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useMemo, useState } from "react";
import { LocaleToggle } from "@/components/shell/locale-toggle";
import { Button } from "@/components/ui/button";
import { ApiError, isApiEnabled, type TokenProvider } from "@/lib/api/client";
import {
  compileChecklist,
  confirmSubtype,
  createMatter as createMatterRequest,
  routeMatter,
  saveIntakeAnswer,
} from "@/lib/api/matters";
import { useTokenProvider } from "@/lib/api/use-token-provider";
import {
  RTA_TAXONOMY,
  statutoryFamilies,
  subtypesInFamily,
  transactionFamilies,
} from "@/lib/rta/taxonomy";
import { useDemoStore } from "@/lib/store";
import { cn } from "@/lib/utils";
import type {
  ApiChecklistItem,
  ApiChecklistSnapshot,
  ApiRouting,
  DispositionScope,
  MandatoryBasis,
  MatterFamilyId,
  ParcelKind,
  PartyContext,
  RequirementGroup,
  RtaSubtypeDefinition,
  TriState,
} from "@/types/rta";
import type { MatterType } from "@/types";

/* ── Closed vocabularies, in the display order questions.py lists them ────── */

/** Q01 and Q06 (`AnswerValueKind.TRI_STATE`). `NOT_APPLICABLE` is not offered
 *  here: neither question has a meaningful "does not apply" reading. */
const TRI_STATE_ANSWERS: readonly TriState[] = ["YES", "NO", "UNKNOWN"];

/** Q03 option values (RTA ss. 47–48). */
const SCOPE_ANSWERS: readonly DispositionScope[] = [
  "WHOLE_REGISTERED_PARCEL",
  "PART_OF_PARCEL",
  "UNDIVIDED_INTEREST",
  "UNKNOWN",
];

/** Q04 option values (ss. 50–52). */
const PARCEL_KIND_ANSWERS: readonly ParcelKind[] = [
  "ORDINARY",
  "CONDOMINIUM_UNIT",
  "CONVERSION_TO_CONDOMINIUM",
  "UNKNOWN",
];

/**
 * Q05 option values. `UNKNOWN` is deliberately not a `PartyContext` member —
 * it records that the screening has not been done and must never collapse into
 * `NATURAL_PERSONS_ONLY` (§4.1, §4.4).
 */
const PARTY_UNKNOWN = "UNKNOWN" as const;
type PartyAnswer = PartyContext | typeof PARTY_UNKNOWN;
const PARTY_CONTEXT_ANSWERS: readonly PartyAnswer[] = [
  "NATURAL_PERSONS_ONLY",
  "COMPANY",
  "ESTATE_OR_DECEASED",
  "ATTORNEY_POWER_OF_ATTORNEY",
  "PUBLIC_BODY",
  "OTHER_NON_INDIVIDUAL",
  PARTY_UNKNOWN,
];

const INSTRUMENT_LANGUAGES = ["en", "si", "ta"] as const;
type InstrumentLanguage = (typeof INSTRUMENT_LANGUAGES)[number];

/** Checklist groups, in the order §11.1 lists them. */
const GROUP_ORDER: readonly RequirementGroup[] = [
  "LEGAL_REGISTRY",
  "TITLE_EXAMINATION",
  "CONDITIONAL",
  "OFFICE_ADDED",
];

const GROUP_MESSAGE_KEYS: Record<RequirementGroup, string> = {
  LEGAL_REGISTRY: "groupLegalRegistry",
  TITLE_EXAMINATION: "groupTitleExamination",
  CONDITIONAL: "groupConditional",
  OFFICE_ADDED: "groupOfficeAdded",
};

const BASIS_MESSAGE_KEYS: Record<MandatoryBasis, string> = {
  LEGAL: "basisLegal",
  REGULATORY: "basisRegulatory",
  OPERATIONAL: "basisOperational",
  LAWYER_POLICY: "basisLawyerPractice",
  PRODUCT_SAFETY: "basisProductSafety",
  LOCAL_AUTHORITY: "basisLocalAuthority",
  CONDITIONAL: "basisConditional",
};

const BASIS_ICONS: Record<MandatoryBasis, typeof Scale> = {
  LEGAL: Scale,
  REGULATORY: Gavel,
  OPERATIONAL: Wrench,
  LAWYER_POLICY: UserCog,
  PRODUCT_SAFETY: ShieldCheck,
  LOCAL_AUTHORITY: Landmark,
  CONDITIONAL: CircleHelp,
};

/** `InclusionReason` in compiler.py. Unknown values fall back to the id. */
const INCLUSION_REASON_KEYS: Record<string, string> = {
  BASE: "inclusionBase",
  REGIME: "inclusionRegime",
  EXACT_INSTRUMENT: "inclusionExactInstrument",
  CONDITIONAL_MODULE: "inclusionConditionalModule",
  OFFICE_POLICY: "inclusionOfficePolicy",
  LOCAL_AUTHORITY_POLICY: "inclusionLocalAuthorityPolicy",
  LAWYER_ADDED: "inclusionLawyerAdded",
  RETAINED_AFTER_REVIEW: "inclusionRetainedAfterReview",
};

/** §3.3 release tiers, as an icon + text badge — never colour alone. */
const TIER_BADGES = {
  V0: { messageKey: "tierV0", icon: FlaskConical },
  V1: { messageKey: "tierPlanned", icon: CircleDashed },
  DEFERRED: { messageKey: "tierPlanned", icon: CircleDashed },
  MANUAL_ONLY: { messageKey: "tierManualOnly", icon: ScrollText },
} as const;

const TOTAL_STEPS = 7;

type FileState = "selected" | "attached" | "pendingUpload";
interface SelectedFile {
  file: File;
  state: FileState;
}

/**
 * `useTokenProvider` calls Clerk's `useAuth`, which requires a `ClerkProvider`.
 * The offline demo runs without one, so the hook lives in a component that is
 * only mounted when the backend is configured. `isApiEnabled()` reads an
 * inlined build-time env var, so the branch never changes between renders and
 * hook order stays stable.
 */
export function NewMatterScreen() {
  return isApiEnabled() ? <ApiBoundNewMatterScreen /> : <NewMatterFlow getToken={null} />;
}

function ApiBoundNewMatterScreen() {
  const getToken = useTokenProvider();
  return <NewMatterFlow getToken={getToken} />;
}

function NewMatterFlow({ getToken }: { getToken: TokenProvider | null }) {
  const t = useTranslations("newMatter");
  /** Rule-pack label keys (`rta.family.*`, `rta.subtype.*`, gate reason keys)
   *  are authored in the rule pack, so they resolve from the message root. */
  const tRoot = useTranslations();
  const router = useRouter();
  const reduceMotion = useReducedMotion();
  const createDemoMatter = useDemoStore((state) => state.createMatter);
  const addDocument = useDemoStore((state) => state.addDocument);
  const markProcessingNotConfigured = useDemoStore((state) => state.markProcessingNotConfigured);

  const [step, setStep] = useState(0);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Step 1 — metadata.
  const [reference, setReference] = useState("");
  const [clientReference, setClientReference] = useState("");
  const [instrumentLanguage, setInstrumentLanguage] = useState<InstrumentLanguage>("en");
  const [lawyerNote, setLawyerNote] = useState("");

  // Steps 2–5 — routing answers.
  const [q01Regime, setQ01Regime] = useState<TriState | null>(null);
  const [familyId, setFamilyId] = useState<MatterFamilyId | null>(null);
  const [subtypeId, setSubtypeId] = useState<string | null>(null);
  const [declaredLegalBasis, setDeclaredLegalBasis] = useState("");
  const [legalBasisConfirmed, setLegalBasisConfirmed] = useState(false);
  const [q03Scope, setQ03Scope] = useState<DispositionScope | null>(null);
  const [q04ParcelKind, setQ04ParcelKind] = useState<ParcelKind | null>(null);
  const [q05PartyContexts, setQ05PartyContexts] = useState<PartyAnswer[]>([]);
  const [q06Dispute, setQ06Dispute] = useState<TriState | null>(null);

  // Server-owned results.
  const [matterId, setMatterId] = useState<string | null>(null);
  const [matterVersion, setMatterVersion] = useState<number | null>(null);
  const [routing, setRouting] = useState<ApiRouting | null>(null);
  const [snapshot, setSnapshot] = useState<ApiChecklistSnapshot | null>(null);
  const [compileState, setCompileState] = useState<"idle" | "loading" | "done" | "failed">("idle");

  // Step 7 — evidence.
  const [files, setFiles] = useState<SelectedFile[]>([]);

  const subtypes = useMemo(
    () => (familyId === null ? [] : subtypesInFamily(familyId)),
    [familyId],
  );
  const selectedSubtype = useMemo(
    () => subtypes.find((candidate) => candidate.id === subtypeId) ?? null,
    [subtypes, subtypeId],
  );
  const needsDeclaredBasis = selectedSubtype?.requiresDeclaredLegalBasis === true;

  const describeError = useCallback(
    (cause: unknown) => (cause instanceof ApiError ? cause.message : t("genericError")),
    [t],
  );

  /** Compile is the one place the flow depends on the server. */
  const runRoutingAndCompile = useCallback(async () => {
    if (getToken === null || matterId === null || matterVersion === null) return;
    setCompileState("loading");
    setError(null);
    try {
      const routed = await routeMatter(getToken, matterId, matterVersion);
      setRouting(routed);
      setMatterVersion(routed.matter.version);
      const compiled = await compileChecklist(getToken, matterId, routed.matter.version);
      setSnapshot(compiled);
      setCompileState("done");
    } catch (cause) {
      setError(describeError(cause));
      setCompileState("failed");
    }
  }, [describeError, getToken, matterId, matterVersion]);

  useEffect(() => {
    if (step === 6 && getToken !== null && compileState === "idle") {
      void runRoutingAndCompile();
    }
  }, [compileState, getToken, runRoutingAndCompile, step]);

  const canContinue = (() => {
    switch (step) {
      case 1:
        return reference.trim().length > 0;
      case 2:
        return q01Regime !== null;
      case 3:
        return familyId !== null;
      case 4:
        if (subtypeId === null) return false;
        return !needsDeclaredBasis || (declaredLegalBasis.trim().length > 0 && legalBasisConfirmed);
      case 5:
        return (
          q03Scope !== null &&
          q04ParcelKind !== null &&
          q05PartyContexts.length > 0 &&
          q06Dispute !== null
        );
      default:
        return true;
    }
  })();

  /**
   * Persist what this step decided, then advance. Every write is skipped when
   * the backend is not configured; the answers stay in component state so Back
   * and Continue still preserve them.
   */
  async function goNext() {
    if (!canContinue || busy) return;
    setError(null);
    if (getToken === null) {
      setStep((value) => Math.min(TOTAL_STEPS, value + 1));
      return;
    }
    setBusy(true);
    try {
      if (step === 1) {
        const created = await createMatterRequest(getToken, {
          reference: reference.trim(),
          ...(clientReference.trim() ? { clientReference: clientReference.trim() } : {}),
          instrumentLanguage,
        });
        setMatterId(created.id);
        setMatterVersion(created.version);
      } else if (step === 2 && matterId !== null && q01Regime !== null) {
        await saveIntakeAnswer(getToken, matterId, "Q01_REGIME", {
          value: q01Regime,
          lawyerConfirmed: true,
          ...(lawyerNote.trim() ? { reason: lawyerNote.trim() } : {}),
        });
      } else if (step === 3 && matterId !== null && familyId !== null) {
        await saveIntakeAnswer(getToken, matterId, "Q02_INTENT", {
          value: familyId,
          lawyerConfirmed: true,
        });
      } else if (step === 4 && matterId !== null && subtypeId !== null && matterVersion !== null) {
        const updated = await confirmSubtype(
          getToken,
          matterId,
          {
            subtypeId,
            ...(declaredLegalBasis.trim()
              ? { declaredLegalBasis: declaredLegalBasis.trim() }
              : {}),
          },
          matterVersion,
        );
        setMatterVersion(updated.version);
      } else if (step === 5 && matterId !== null) {
        // Saved one at a time: each answer is its own record with its own
        // provenance, and PUT supersedes rather than overwrites (§4.4).
        if (q03Scope !== null) {
          await saveIntakeAnswer(getToken, matterId, "Q03_SCOPE", {
            value: q03Scope,
            lawyerConfirmed: true,
          });
        }
        if (q04ParcelKind !== null) {
          await saveIntakeAnswer(getToken, matterId, "Q04_PARCEL_KIND", {
            value: q04ParcelKind,
            lawyerConfirmed: true,
          });
        }
        await saveIntakeAnswer(getToken, matterId, "Q05_PARTY_CONTEXT", {
          value: q05PartyContexts,
          lawyerConfirmed: true,
        });
        if (q06Dispute !== null) {
          await saveIntakeAnswer(getToken, matterId, "Q06_DISPUTE", {
            value: q06Dispute,
            lawyerConfirmed: true,
          });
        }
        setCompileState("idle");
      }
      setStep((value) => Math.min(TOTAL_STEPS, value + 1));
    } catch (cause) {
      setError(describeError(cause));
    } finally {
      setBusy(false);
    }
  }

  /**
   * Finish. The matter already exists at this point in API mode — uploading is
   * not part of creating it (§4.2 Q07), so files are attached afterwards.
   */
  function finish() {
    if (matterId !== null) {
      // No ingestion endpoint exists yet, so the selected files are held for
      // attachment rather than reported as uploaded.
      setFiles((current) => current.map((entry) => ({ ...entry, state: "pendingUpload" })));
      router.push(`/matters/${matterId}`);
      return;
    }
    const demoId = createDemoMatter({
      reference: reference.trim() || t("matterPlaceholder"),
      ...(clientReference.trim() ? { clientReference: clientReference.trim() } : {}),
      regime: "rta",
      type: legacyTypeForSubtype(subtypeId),
    });
    files.forEach((entry) => {
      const documentId = addDocument(entry.file.name, "other", demoId);
      // No extraction provider runs in the offline demo, so the file is
      // recorded as awaiting processing. Nothing here may claim "processed".
      markProcessingNotConfigured(documentId);
    });
    setFiles((current) => current.map((entry) => ({ ...entry, state: "attached" })));
    router.push(`/matters/${demoId}`);
  }

  if (step === 0) {
    return (
      <main className="bg-canvas min-h-screen">
        <header className="absolute inset-x-0 top-0 z-10 flex h-16 items-center px-6">
          <div className="font-heading text-ink text-3xl font-semibold">{t("entryTitle")}</div>
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
                <h1 className="mt-2 text-6xl font-semibold sm:text-7xl">{t("entryTitle")}</h1>
                <p className="text-ink mt-4 max-w-lg text-lg leading-8">{t("entryBody")}</p>
              </motion.div>
            </div>
            <div className="border-border-strong bg-surface/95 border-t px-6 py-5 sm:px-12 lg:px-20">
              <div className="flex flex-wrap items-end gap-4">
                <div className="min-w-0 flex-1">
                  <h2 className="text-2xl font-semibold">{t("chooseRegime")}</h2>
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
                <Button variant="primary" onClick={() => setStep(1)}>
                  {t("continue")}
                  <ArrowRight className="size-4" strokeWidth={1.5} />
                </Button>
              </div>
            </div>
          </div>
        </section>
      </main>
    );
  }

  return (
    <main className="bg-canvas min-h-screen">
      <header className="border-border bg-surface flex h-16 items-center border-b px-6">
        <div className="font-heading text-2xl font-semibold">{t("entryTitle")}</div>
        <div className="ml-auto">
          <LocaleToggle />
        </div>
      </header>
      <div className="mx-auto max-w-3xl p-6 sm:p-10">
        <div className="text-muted-ink text-xs font-semibold uppercase">
          {t("stepOf", { current: step, total: TOTAL_STEPS })}
        </div>

        {step === 1 && (
          <section className="mt-3">
            <h1 className="text-4xl font-semibold">{t("metadataTitle")}</h1>
            <p className="text-muted-ink mt-2">{t("metadataBody")}</p>
            <div className="border-amber bg-amber-bg text-amber-text mt-4 border-l-2 p-3 text-sm">
              {t("privacy")}
            </div>
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
            <fieldset className="mt-6">
              <legend className="font-medium">{t("instrumentLanguage")}</legend>
              <p className="text-muted-ink text-sm">{t("instrumentLanguageHint")}</p>
              <div className="mt-2 flex flex-wrap gap-2">
                {INSTRUMENT_LANGUAGES.map((language) => (
                  <ChoiceButton
                    key={language}
                    selected={instrumentLanguage === language}
                    onSelect={() => setInstrumentLanguage(language)}
                    label={t(`language.${language}`)}
                  />
                ))}
              </div>
            </fieldset>
            <label className="mt-6 block font-medium">
              {t("responsibleLawyerNote")}
              <span className="text-muted-ink block text-sm font-normal">
                {t("responsibleLawyerNoteHint")}
              </span>
              <textarea
                className="border-border-strong bg-surface mt-1 min-h-24 w-full rounded border p-3"
                value={lawyerNote}
                onChange={(event) => setLawyerNote(event.target.value)}
              />
            </label>
          </section>
        )}

        {step === 2 && (
          <section className="mt-3">
            <h1 className="text-4xl font-semibold">{t("titleSystemTitle")}</h1>
            <p className="text-muted-ink mt-2">{t("q01Prompt")}</p>
            <div className="mt-6 flex flex-wrap gap-2">
              {TRI_STATE_ANSWERS.map((answer) => (
                <ChoiceButton
                  key={answer}
                  selected={q01Regime === answer}
                  onSelect={() => setQ01Regime(answer)}
                  label={t(`answer.${answer}`)}
                />
              ))}
            </div>
            <p className="text-muted-ink mt-3 flex items-start gap-2 text-sm">
              <CircleHelp className="mt-0.5 size-4 shrink-0" strokeWidth={1.5} aria-hidden="true" />
              {t("unknownIsAcceptable")}
            </p>
            <p className="text-muted-ink mt-4 text-sm">{t("q01Why")}</p>
            {(q01Regime === "NO" || q01Regime === "UNKNOWN") && (
              <div className="border-border-strong bg-selected-bg mt-6 rounded border p-4">
                <h2 className="flex items-center gap-2 text-lg font-semibold">
                  <ScrollText className="size-5" strokeWidth={1.5} aria-hidden="true" />
                  {t("initialCompilationTitle")}
                </h2>
                <p className="mt-2 text-sm">{t("initialCompilationBody")}</p>
                <p className="text-muted-ink mt-2 text-sm">{t("initialCompilationContinue")}</p>
              </div>
            )}
          </section>
        )}

        {step === 3 && (
          <section className="mt-3">
            <h1 className="text-4xl font-semibold">{t("familyTitle")}</h1>
            <p className="text-muted-ink mt-2">{t("q02Prompt")}</p>
            <h2 className="text-muted-ink mt-6 text-xs font-semibold uppercase">
              {t("familyTransactionsHeading")}
            </h2>
            <div className="mt-2 grid gap-2 sm:grid-cols-2">
              {transactionFamilies().map((family) => (
                <FamilyCard
                  key={family.id}
                  selected={familyId === family.id}
                  onSelect={() => {
                    setFamilyId(family.id);
                    setSubtypeId(null);
                  }}
                  title={tRoot(family.labelKey)}
                  purpose={tRoot(family.purposeKey)}
                />
              ))}
            </div>
            <h2 className="text-muted-ink border-border mt-8 border-t pt-6 text-xs font-semibold uppercase">
              {t("familyStatutoryHeading")}
            </h2>
            <p className="text-muted-ink mt-1 text-sm">{t("familyStatutoryBody")}</p>
            <div className="mt-2 grid gap-2 sm:grid-cols-2">
              {statutoryFamilies()
                .filter((family) => family.id !== "controlled_other")
                .map((family) => (
                  <FamilyCard
                    key={family.id}
                    selected={familyId === family.id}
                    onSelect={() => {
                      setFamilyId(family.id);
                      setSubtypeId(null);
                    }}
                    title={tRoot(family.labelKey)}
                    purpose={tRoot(family.purposeKey)}
                  />
                ))}
            </div>
            <h2 className="text-muted-ink border-border mt-8 border-t pt-6 text-xs font-semibold uppercase">
              {t("familyOtherHeading")}
            </h2>
            <div className="mt-2">
              {statutoryFamilies()
                .filter((family) => family.id === "controlled_other")
                .map((family) => (
                  <FamilyCard
                    key={family.id}
                    muted
                    selected={familyId === family.id}
                    onSelect={() => {
                      setFamilyId(family.id);
                      setSubtypeId(null);
                    }}
                    title={tRoot(family.labelKey)}
                    purpose={t("familyOtherNote")}
                  />
                ))}
            </div>
          </section>
        )}

        {step === 4 && (
          <section className="mt-3">
            <h1 className="text-4xl font-semibold">{t("subtypeTitle")}</h1>
            <p className="text-muted-ink mt-2">{t("subtypeBody")}</p>
            <ul className="mt-6 grid gap-2">
              {subtypes.map((subtype) => (
                <li key={subtype.id}>
                  <SubtypeRow
                    subtype={subtype}
                    selected={subtypeId === subtype.id}
                    onSelect={() => setSubtypeId(subtype.id)}
                    label={tRoot(subtype.labelKey)}
                    formLabel={
                      subtype.gazetteFormNumber === null
                        ? t("noGazetteForm")
                        : t("gazetteForm", { number: subtype.gazetteFormNumber })
                    }
                    tierLabel={t(TIER_BADGES[subtype.releaseTier].messageKey)}
                    TierIcon={TIER_BADGES[subtype.releaseTier].icon}
                  />
                </li>
              ))}
            </ul>
            {needsDeclaredBasis && (
              <div className="border-border-strong bg-surface mt-6 rounded border p-4">
                <label className="block font-medium">
                  {t("legalBasisLabel")}
                  <span className="text-muted-ink block text-sm font-normal">
                    {t("legalBasisHint")}
                  </span>
                  <textarea
                    required
                    className="border-border-strong bg-surface mt-2 min-h-28 w-full rounded border p-3"
                    value={declaredLegalBasis}
                    onChange={(event) => setDeclaredLegalBasis(event.target.value)}
                  />
                </label>
                <label className="mt-3 flex items-start gap-2 text-sm font-medium">
                  <input
                    type="checkbox"
                    className="mt-0.5 size-4"
                    checked={legalBasisConfirmed}
                    onChange={(event) => setLegalBasisConfirmed(event.target.checked)}
                  />
                  {t("legalBasisConfirm")}
                </label>
              </div>
            )}
          </section>
        )}

        {step === 5 && (
          <section className="mt-3">
            <h1 className="text-4xl font-semibold">{t("routingTitle")}</h1>
            <p className="text-muted-ink mt-2">{t("routingBody")}</p>

            <QuestionBlock prompt={t("q03Prompt")}>
              {SCOPE_ANSWERS.map((answer) => (
                <ChoiceButton
                  key={answer}
                  selected={q03Scope === answer}
                  onSelect={() => setQ03Scope(answer)}
                  label={t(`scope.${answer}`)}
                />
              ))}
            </QuestionBlock>

            <QuestionBlock prompt={t("q04Prompt")}>
              {PARCEL_KIND_ANSWERS.map((answer) => (
                <ChoiceButton
                  key={answer}
                  selected={q04ParcelKind === answer}
                  onSelect={() => setQ04ParcelKind(answer)}
                  label={t(`parcelKind.${answer}`)}
                />
              ))}
            </QuestionBlock>

            <QuestionBlock prompt={t("q05Prompt")} hint={t("q05Hint")}>
              {PARTY_CONTEXT_ANSWERS.map((answer) => (
                <ChoiceButton
                  key={answer}
                  multi
                  selected={q05PartyContexts.includes(answer)}
                  onSelect={() => setQ05PartyContexts(togglePartyContext(q05PartyContexts, answer))}
                  label={t(`partyContext.${answer}`)}
                />
              ))}
            </QuestionBlock>

            <QuestionBlock prompt={t("q06Prompt")} hint={t("q06Hint")}>
              {TRI_STATE_ANSWERS.map((answer) => (
                <ChoiceButton
                  key={answer}
                  selected={q06Dispute === answer}
                  onSelect={() => setQ06Dispute(answer)}
                  label={t(`answer.${answer}`)}
                />
              ))}
            </QuestionBlock>
          </section>
        )}

        {step === 6 && (
          <section className="mt-3">
            <h1 className="text-4xl font-semibold">{t("checklistTitle")}</h1>
            <p className="text-muted-ink mt-2">{t("checklistBody")}</p>

            {getToken === null && (
              <div className="border-border-strong bg-surface mt-6 rounded border p-4">
                <h2 className="flex items-center gap-2 text-lg font-semibold">
                  <AlertCircle className="size-5" strokeWidth={1.5} aria-hidden="true" />
                  {t("compilerUnavailableTitle")}
                </h2>
                <p className="mt-2 text-sm">{t("compilerUnavailableBody")}</p>
              </div>
            )}

            {getToken !== null && compileState === "loading" && (
              <p className="text-muted-ink mt-6 flex items-center gap-2">
                <LoaderCircle className="size-5 animate-spin" strokeWidth={1.5} aria-hidden="true" />
                {t("compiling")}
              </p>
            )}

            {getToken !== null && compileState === "failed" && (
              <div className="border-amber bg-amber-bg text-amber-text mt-6 rounded border p-4">
                <h2 className="flex items-center gap-2 font-semibold">
                  <AlertCircle className="size-5" strokeWidth={1.5} aria-hidden="true" />
                  {t("compileFailedTitle")}
                </h2>
                <p className="mt-2 text-sm">{t("compileFailedBody")}</p>
                <Button
                  className="mt-3"
                  onClick={() => {
                    setCompileState("idle");
                  }}
                >
                  {t("retry")}
                </Button>
              </div>
            )}

            {routing !== null && (
              <div
                className={cn(
                  "mt-6 rounded border p-4",
                  routing.automationScope === "V0_AUTOMATED"
                    ? "border-forest bg-soft-green"
                    : "border-border-strong bg-selected-bg",
                )}
              >
                <h2 className="flex items-center gap-2 text-lg font-semibold">
                  {routing.automationScope === "V0_AUTOMATED" ? (
                    <Check className="size-5" strokeWidth={1.5} aria-hidden="true" />
                  ) : (
                    <UserCog className="size-5" strokeWidth={1.5} aria-hidden="true" />
                  )}
                  {routing.automationScope === "V0_AUTOMATED"
                    ? t("scopeAutomatedTitle")
                    : t("scopeManualTitle")}
                </h2>
                <p className="mt-2 text-sm">
                  {routing.automationScope === "V0_AUTOMATED"
                    ? t("scopeAutomatedBody")
                    : t("scopeManualBody")}
                </p>
                {routing.automationScope !== "V0_AUTOMATED" && (
                  <>
                    <h3 className="mt-3 text-xs font-semibold uppercase">
                      {t("unmetGatesHeading")}
                    </h3>
                    <ul className="mt-1 list-disc pl-5 text-sm">
                      {routing.gates
                        .filter((gate) => !gate.satisfied)
                        .map((gate) => (
                          <li key={gate.id}>{tRoot(gate.reasonKey)}</li>
                        ))}
                    </ul>
                  </>
                )}
              </div>
            )}

            {snapshot !== null &&
              GROUP_ORDER.map((group) => {
                const items = snapshot.items.filter((item) => item.group === group);
                if (items.length === 0) return null;
                return (
                  <div key={group} className="mt-6">
                    <h2 className="text-muted-ink text-xs font-semibold uppercase">
                      {t(GROUP_MESSAGE_KEYS[group])}
                    </h2>
                    <ul className="divide-border border-border mt-2 divide-y border-y">
                      {items.map((item) => (
                        <ChecklistRow
                          key={item.requirementDefinitionId}
                          item={item}
                          label={tRoot(item.labelKey)}
                          reason={inclusionText(item, t)}
                          basisLabel={t(BASIS_MESSAGE_KEYS[item.mandatoryBasis])}
                        />
                      ))}
                    </ul>
                  </div>
                );
              })}
          </section>
        )}

        {step === 7 && (
          <section className="mt-3">
            <h1 className="text-4xl font-semibold">{t("uploadTitle")}</h1>
            <p className="text-muted-ink mt-2">{t("uploadBody")}</p>
            <label className="border-border-strong bg-surface hover:bg-hover-bg mt-6 flex min-h-48 cursor-pointer flex-col items-center justify-center rounded border border-dashed p-6 text-center">
              <Upload className="text-forest size-6" strokeWidth={1.5} aria-hidden="true" />
              <span className="mt-2 font-medium">{t("chooseDocuments")}</span>
              <span className="mt-1 text-sm font-medium">{t("uploadRecommended")}</span>
              <span className="text-muted-ink mt-1 text-sm">
                {t("selectedFiles", { count: files.length })}
              </span>
              <input
                className="sr-only"
                type="file"
                multiple
                accept="application/pdf,image/*"
                onChange={(event) =>
                  setFiles(
                    Array.from(event.target.files ?? []).map((file) => ({
                      file,
                      state: "selected" as const,
                    })),
                  )
                }
              />
            </label>
            <p className="text-muted-ink mt-3 text-sm">{t("uploadLimits")}</p>
            <div className="border-amber bg-amber-bg text-amber-text mt-3 border-l-2 p-3 text-sm">
              {t("uploadConfidentiality")}
            </div>
            {files.length > 0 && (
              <ul className="divide-border border-border mt-4 divide-y border-y">
                {files.map((entry, index) => (
                  <li
                    key={`${entry.file.name}-${index}`}
                    className="flex min-h-11 items-center gap-3 py-2 text-sm"
                  >
                    <span className="min-w-0 flex-1 truncate">{entry.file.name}</span>
                    <span className="border-border-strong text-muted-ink inline-flex items-center gap-1.5 rounded-full border px-2 py-1 text-xs font-semibold">
                      <CircleDashed className="size-4" strokeWidth={1.5} aria-hidden="true" />
                      {t(`fileState.${entry.state}`)}
                    </span>
                  </li>
                ))}
              </ul>
            )}
            {getToken !== null && files.length > 0 && (
              <p className="text-muted-ink mt-3 text-sm">{t("uploadPendingIngestion")}</p>
            )}
          </section>
        )}

        {error !== null && (
          <p role="alert" className="border-red bg-red-bg text-red mt-6 rounded border p-3 text-sm">
            {error}
          </p>
        )}

        <footer className="border-border mt-8 flex gap-2 border-t pt-4">
          <Button onClick={() => setStep((value) => Math.max(0, value - 1))} disabled={busy}>
            <ArrowLeft className="size-4" strokeWidth={1.5} aria-hidden="true" />
            {t("back")}
          </Button>
          {step < TOTAL_STEPS ? (
            <Button
              className="ml-auto"
              variant="primary"
              disabled={!canContinue || busy}
              onClick={() => void goNext()}
            >
              {busy ? t("saving") : t("next")}
              <ArrowRight className="size-4" strokeWidth={1.5} aria-hidden="true" />
            </Button>
          ) : (
            <Button className="ml-auto" variant="primary" disabled={busy} onClick={finish}>
              {t("create")}
              <ArrowRight className="size-4" strokeWidth={1.5} aria-hidden="true" />
            </Button>
          )}
        </footer>
      </div>
    </main>
  );
}

/* ── Pure helpers ─────────────────────────────────────────────────────────── */

/**
 * `UNKNOWN` is exclusive: it means the screening has not been done, so it
 * cannot coexist with an asserted party context, and asserting one clears it.
 * Nothing here maps `UNKNOWN` onto `NATURAL_PERSONS_ONLY`.
 */
function togglePartyContext(current: PartyAnswer[], answer: PartyAnswer): PartyAnswer[] {
  if (current.includes(answer)) return current.filter((value) => value !== answer);
  if (answer === PARTY_UNKNOWN) return [PARTY_UNKNOWN];
  return [...current.filter((value) => value !== PARTY_UNKNOWN), answer];
}

function inclusionText(item: ApiChecklistItem, t: (key: string) => string): string {
  const messageKey = INCLUSION_REASON_KEYS[item.inclusionReason];
  const reason = messageKey === undefined ? item.inclusionReason : t(messageKey);
  return item.inclusionTriggerId === null ? reason : `${reason} · ${item.inclusionTriggerId}`;
}

/**
 * Derive the deprecated M2 `MatterType` for the offline demo store, which still
 * requires it. Reverses the rule pack's own legacy map rather than guessing, and
 * falls back to `other` — the coarse label is never the authority for what the
 * instrument is (§3.6).
 */
function legacyTypeForSubtype(subtypeId: string | null): MatterType {
  if (subtypeId === null) return "other";
  const match = Object.entries(RTA_TAXONOMY.legacyMatterTypeMap).find(
    ([, mapped]) => mapped === subtypeId,
  );
  const legacy = match?.[0];
  return legacy === "transfer" || legacy === "gift" || legacy === "lease" || legacy === "mortgage"
    ? legacy
    : "other";
}

/* ── Presentational pieces ────────────────────────────────────────────────── */

function QuestionBlock({
  prompt,
  hint,
  children,
}: {
  prompt: string;
  hint?: string;
  children: React.ReactNode;
}) {
  return (
    <fieldset className="border-border mt-6 border-t pt-4">
      <legend className="sr-only">{prompt}</legend>
      <p className="font-medium">{prompt}</p>
      {hint !== undefined && <p className="text-muted-ink mt-1 text-sm">{hint}</p>}
      <div className="mt-2 flex flex-wrap gap-2">{children}</div>
    </fieldset>
  );
}

function ChoiceButton({
  selected,
  onSelect,
  label,
  multi = false,
}: {
  selected: boolean;
  onSelect: () => void;
  label: string;
  multi?: boolean;
}) {
  return (
    <button
      type="button"
      role={multi ? "checkbox" : undefined}
      aria-checked={multi ? selected : undefined}
      aria-pressed={multi ? undefined : selected}
      onClick={onSelect}
      className={cn(
        "inline-flex min-h-10 items-center gap-2 rounded border px-3 py-2 text-left font-medium",
        selected
          ? "border-forest bg-selected-bg text-forest"
          : "border-border-strong bg-surface hover:bg-hover-bg",
      )}
    >
      {selected && <Check className="size-4" strokeWidth={1.5} aria-hidden="true" />}
      {label}
    </button>
  );
}

function FamilyCard({
  selected,
  onSelect,
  title,
  purpose,
  muted = false,
}: {
  selected: boolean;
  onSelect: () => void;
  title: string;
  purpose: string;
  muted?: boolean;
}) {
  return (
    <button
      type="button"
      aria-pressed={selected}
      onClick={onSelect}
      className={cn(
        "flex min-h-20 w-full flex-col items-start gap-1 rounded border p-4 text-left",
        selected
          ? "border-forest bg-selected-bg"
          : "border-border-strong bg-surface hover:bg-hover-bg",
        muted && !selected && "border-border text-muted-ink bg-canvas",
      )}
    >
      <span className="flex w-full items-center gap-2 font-semibold">
        {title}
        {selected && <Check className="ml-auto size-4" strokeWidth={1.5} aria-hidden="true" />}
      </span>
      <span className="text-muted-ink text-sm">{purpose}</span>
    </button>
  );
}

function SubtypeRow({
  subtype,
  selected,
  onSelect,
  label,
  formLabel,
  tierLabel,
  TierIcon,
}: {
  subtype: RtaSubtypeDefinition;
  selected: boolean;
  onSelect: () => void;
  label: string;
  formLabel: string;
  tierLabel: string;
  TierIcon: typeof FlaskConical;
}) {
  return (
    <button
      type="button"
      aria-pressed={selected}
      onClick={onSelect}
      className={cn(
        "flex min-h-14 w-full items-center gap-3 rounded border p-3 text-left",
        selected
          ? "border-forest bg-selected-bg"
          : "border-border-strong bg-surface hover:bg-hover-bg",
      )}
    >
      <span className="min-w-0 flex-1">
        <span className="block font-medium">{label}</span>
        <span className="text-muted-ink block text-sm tabular-nums">{formLabel}</span>
      </span>
      <span
        data-release-tier={subtype.releaseTier}
        className="border-border-strong inline-flex min-h-7 shrink-0 items-center gap-1.5 rounded-full border px-2 py-1 text-xs font-semibold"
      >
        <TierIcon className="size-4" strokeWidth={1.5} aria-hidden="true" />
        {tierLabel}
      </span>
      {selected && <Check className="size-4 shrink-0" strokeWidth={1.5} aria-hidden="true" />}
    </button>
  );
}

function ChecklistRow({
  item,
  label,
  reason,
  basisLabel,
}: {
  item: ApiChecklistItem;
  label: string;
  reason: string;
  basisLabel: string;
}) {
  const BasisIcon = BASIS_ICONS[item.mandatoryBasis];
  return (
    <li className="flex min-h-11 flex-wrap items-start gap-x-3 gap-y-1 py-2.5">
      <span className="min-w-0 flex-1">
        <span className="block font-medium">{label}</span>
        <span className="text-muted-ink block text-sm">{reason}</span>
      </span>
      <span
        data-mandatory-basis={item.mandatoryBasis}
        className="border-border-strong inline-flex min-h-7 shrink-0 items-center gap-1.5 rounded-full border px-2 py-1 text-xs font-semibold"
      >
        <BasisIcon className="size-4" strokeWidth={1.5} aria-hidden="true" />
        {basisLabel}
      </span>
    </li>
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
      type="button"
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
