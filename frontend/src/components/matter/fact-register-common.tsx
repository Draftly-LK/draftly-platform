"use client";
import { useRef } from "react";
import { useTranslations } from "next-intl";
import {
  AlertCircle,
  CheckCircle2,
  History,
  Info,
  PencilLine,
  XCircle,
} from "lucide-react";
import { ApiError } from "@/lib/api/client";
import { useEnumLabel } from "@/lib/i18n/use-enum-label";
import type {
  ApiFactType,
  ApiFactValue,
  ApiMatterFact,
  ApiMatterSubject,
} from "@/types/rta";

export const controlClass =
  "mt-1 w-full min-w-0 rounded-control border border-border-control bg-surface px-3 py-2 text-sm";
export function useIntentKey() {
  const intent = useRef<{ signature: string; key: string } | null>(null);
  return Object.assign(
    (signature: string) => {
      if (intent.current?.signature !== signature)
        intent.current = { signature, key: crypto.randomUUID() };
      return intent.current.key;
    },
    {
      reset: () => {
        intent.current = null;
      },
    },
  );
}
export function factValue(value: ApiFactValue): string {
  return value === null ? "—" : String(value);
}
export function useFactDisplayValue() {
  const root = useTranslations();
  const t = useTranslations("factRegister");
  return (value: ApiFactValue, definition?: ApiFactType) => {
    if (typeof value === "boolean")
      return t(value ? "trueValue" : "falseValue");
    const option =
      definition?.valueKind === "ENUM"
        ? definition.options?.find((option) => option.value === value)
        : undefined;
    return option && root.has(option.labelKey)
      ? root(option.labelKey)
      : factValue(value);
  };
}
export function subjectContext(
  subject: ApiMatterSubject,
  facts: ApiMatterFact[],
): string {
  const identities =
    subject.kind === "party"
      ? [
          "holderNameEn",
          "holderNameSi",
          "transferorName",
          "transfereeName",
          "ownerName",
        ]
      : ["parcelNo", "landName"];
  return facts
    .filter(
      (f) =>
        f.subjectId === subject.id &&
        ["LAWYER_CONFIRMED", "LOCKED_FOR_FORM"].includes(f.status) &&
        !f.evidenceStale &&
        identities.includes(f.fieldKey ?? ""),
    )
    .map((f) => factValue(f.value))
    .filter((value, index, items) => items.indexOf(value) === index)
    .join(" / ");
}
export function Status({ fact }: { fact: ApiMatterFact }) {
  const label = useEnumLabel("enums.factStatus");
  const Icon =
    fact.status === "REJECTED"
      ? XCircle
      : fact.status === "SUPERSEDED"
        ? History
        : ["LAWYER_CONFIRMED", "LOCKED_FOR_FORM"].includes(fact.status)
          ? CheckCircle2
          : fact.status === "CONFLICTED"
            ? AlertCircle
            : Info;
  return (
    <span className="inline-flex items-center gap-1 text-sm">
      <Icon aria-hidden="true" className="size-4 shrink-0" strokeWidth={1.5} />
      {label(fact.status)}
    </span>
  );
}
export function RegisterError({ cause }: { cause: unknown }) {
  const t = useTranslations("factRegister");
  const key =
    cause instanceof ApiError && [401, 403].includes(cause.status)
      ? "permissionRefused"
      : cause instanceof ApiError && cause.status === 404
        ? "recordUnavailable"
        : cause instanceof ApiError && [409, 422].includes(cause.status)
          ? "decisionRefused"
          : "apiUnavailable";
  return (
    <div
      role="alert"
      className="border-red bg-red-bg text-red flex gap-2 rounded border p-3 text-sm"
    >
      <AlertCircle aria-hidden="true" className="size-4 shrink-0" />
      <div>
        <p>{t(key)}</p>
        {key === "decisionRefused" && cause instanceof ApiError && (
          <p lang="en" className="mt-1 break-words">
            {cause.message}
          </p>
        )}
      </div>
    </div>
  );
}
export function ValueInput({
  label,
  definition,
  value,
  onChange,
  disabled = false,
}: {
  label: string;
  definition?: ApiFactType;
  value: string;
  onChange: (value: string) => void;
  disabled?: boolean;
}) {
  const t = useTranslations("factRegister");
  const root = useTranslations();
  if (definition?.valueKind === "BOOLEAN")
    return (
      <label className="block text-sm font-medium">
        {label}
        <select
          className={controlClass}
          value={value}
          onChange={(e) => onChange(e.target.value)}
          disabled={disabled}
        >
          <option value="">{t("chooseValue")}</option>
          <option value="true">{t("trueValue")}</option>
          <option value="false">{t("falseValue")}</option>
        </select>
      </label>
    );
  if (definition?.valueKind === "ENUM") {
    if (!definition.options?.length)
      return (
        <div className="text-sm">
          <PencilLine aria-hidden="true" className="mr-1 inline size-4" />
          {t("enumUnavailable")}
        </div>
      );
    return (
      <label className="block text-sm font-medium">
        {label}
        <select
          className={controlClass}
          value={value}
          onChange={(e) => onChange(e.target.value)}
          disabled={disabled}
        >
          <option value="">{t("chooseValue")}</option>
          {definition.options.map((option) => (
            <option key={option.value} value={option.value}>
              {root.has(option.labelKey)
                ? root(option.labelKey)
                : t("unknownFactType")}
            </option>
          ))}
        </select>
      </label>
    );
  }
  return (
    <label className="block text-sm font-medium">
      {label}
      <input
        className={controlClass}
        type={definition?.valueKind === "COUNT" ? "number" : "text"}
        step={definition?.valueKind === "COUNT" ? "1" : undefined}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        disabled={disabled}
      />
    </label>
  );
}
export function inputValue(
  value: string,
  definition?: ApiFactType,
): ApiFactValue {
  if (definition?.valueKind === "BOOLEAN") return value === "true";
  if (definition?.valueKind === "COUNT") return Number(value);
  return value.trim();
}
