"use client";

import { NodeViewWrapper, type NodeViewProps } from "@tiptap/react";
import { CircleCheck, CircleDashed, TriangleAlert } from "lucide-react";
import { useTranslations } from "next-intl";
import { fieldStatus, printedValue, type FieldStatus } from "@/lib/gazette-forms/field-state";
import { cn } from "@/lib/utils";
import { useGazette } from "./gazette-context";
import { useSlotLabel } from "./slot-label";

const STATUS_ICON: Record<FieldStatus, typeof CircleCheck> = {
  confirmed: CircleCheck,
  awaiting: CircleDashed,
  unresolved: TriangleAlert,
};

/**
 * One blank on the printed form. A bound blank prints the backend field's
 * value and opens its review; a free blank is typed into directly. Neither
 * changes the document: values live in the shared gazette context.
 */
export function SlotView({ node }: NodeViewProps) {
  const t = useTranslations("gazette");
  const label = useSlotLabel();
  const { values, setValue, fields, slots, activeSlotId, activate, readOnly, plain } = useGazette();
  const id = String(node.attrs.id);
  const slot = slots[id];
  const size = String(node.attrs.size);
  const active = activeSlotId === id;
  const name = slot ? label(slot) : id;

  if (plain) {
    return (
      <NodeViewWrapper as="span" className={cn("gz-slot", `gz-size-${size}`)} data-gz-slot={id}>
        <span className={cn("gz-blank", node.attrs.bare && "gz-bare-blank")} aria-hidden="true" />
      </NodeViewWrapper>
    );
  }

  if (node.attrs.field) {
    const field = fields[String(node.attrs.field)];
    const status: FieldStatus = field ? fieldStatus(field) : "unresolved";
    const Icon = STATUS_ICON[status];
    const value = field ? printedValue(field) : null;
    return (
      <NodeViewWrapper as="span" className={cn("gz-slot", "gz-slot-bound", `gz-size-${size}`)} data-gz-slot={id}>
        <button
          type="button"
          data-status={status}
          data-active={active ? "" : undefined}
          aria-label={`${name}: ${value ?? t("status.unresolved")} (${t(`status.${status}`)})`}
          aria-pressed={active}
          className="gz-bound"
          onClick={() => activate(id)}
        >
          <span className="gz-bound-value">{value ?? " "}</span>
          <Icon className="gz-bound-icon" strokeWidth={1.5} aria-hidden="true" />
        </button>
      </NodeViewWrapper>
    );
  }

  const shared = {
    "aria-label": name,
    value: values[id] ?? "",
    readOnly,
    "data-active": active ? "" : undefined,
    className: cn("gz-input", node.attrs.bare && "gz-bare"),
    onFocus: () => activate(id),
  };
  return (
    <NodeViewWrapper as="span" className={cn("gz-slot", `gz-size-${size}`)} data-gz-slot={id}>
      {node.attrs.multiline ? (
        <textarea
          {...shared}
          rows={1}
          onChange={(event) => setValue(id, event.target.value)}
        />
      ) : (
        <input
          {...shared}
          type="text"
          onChange={(event) => setValue(id, event.target.value)}
        />
      )}
    </NodeViewWrapper>
  );
}
