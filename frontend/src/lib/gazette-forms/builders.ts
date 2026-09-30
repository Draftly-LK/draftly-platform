import type { JSONContent } from "@tiptap/core";

/**
 * Builders for the gazette template documents.
 *
 * A template is a Tiptap/ProseMirror document whose text is the prescribed
 * wording, transcribed verbatim, and whose blanks are `gzSlot` atoms. The text
 * is never edited: the editor's lock plugin refuses every document change, and
 * what a lawyer writes into a blank lives beside the document (see
 * `SlotValues`), keyed by the slot id.
 */

export type LineVariant =
  | "formNumber"
  | "title"
  | "act"
  | "sectionRef"
  | "boxHeader"
  | "text"
  | "itemTitle"
  | "entry"
  | "para"
  | "note"
  | "centerHeading"
  | "signature";

export type LineAlign = "start" | "center" | "end";

/** How wide a blank is drawn. Mirrors the dotted leader length on the page. */
export type SlotSize = "xs" | "sm" | "md" | "lg" | "xl" | "fill";

export interface SlotOptions {
  /** Backend `GeneratedFormField.fieldId` this blank renders, if any. */
  field?: string;
  size?: SlotSize;
  multiline?: boolean;
  /** Blank drawn without a dotted leader (the page prints only a caption). */
  bare?: boolean;
  /** `gazette.slot.*` translation key, for blanks inside running prose. */
  labelKey?: string;
}

export type Inline = string | JSONContent;

export function slot(id: string, options: SlotOptions = {}): JSONContent {
  return {
    type: "gzSlot",
    attrs: {
      id,
      field: options.field ?? null,
      size: options.size ?? "fill",
      multiline: options.multiline ?? false,
      bare: options.bare ?? false,
      labelKey: options.labelKey ?? null,
    },
  };
}

/** A forced line break inside a line or table cell, as printed. */
export const br: JSONContent = { type: "hardBreak" };

function inlines(parts: Inline[]): JSONContent[] | undefined {
  const content = parts
    .filter((part) => part !== "")
    .map((part) => (typeof part === "string" ? { type: "text", text: part } : part));
  return content.length > 0 ? content : undefined;
}

export function line(
  variant: LineVariant,
  parts: Inline[] = [],
  options: { align?: LineAlign; indent?: boolean; space?: boolean } = {},
): JSONContent {
  return {
    type: "gzLine",
    attrs: {
      variant,
      align: options.align ?? "start",
      indent: options.indent ?? false,
      space: options.space ?? false,
    },
    content: inlines(parts),
  };
}

/** A numbered item: the number hangs in the gutter, as on the page. */
export function item(number: string, children: JSONContent[]): JSONContent {
  return { type: "gzItem", attrs: { number }, content: children };
}

/**
 * Lines that flow row by row across `cols` columns. `signatures` lays each
 * column out as the printed signature block: a fixed-width block, the right
 * one set in from the margin, captions centred under the dotted line.
 */
export function grid(
  children: JSONContent[],
  cols = 2,
  variant: "fields" | "signatures" = "fields",
): JSONContent {
  return { type: "gzGrid", attrs: { cols, variant }, content: children };
}

export function signatures(children: JSONContent[]): JSONContent {
  return grid(children, 2, "signatures");
}

export function box(children: JSONContent[]): JSONContent {
  return { type: "gzBox", content: children };
}

export function columns(children: JSONContent[]): JSONContent {
  return { type: "gzColumns", content: children };
}

export function column(children: JSONContent[]): JSONContent {
  return { type: "gzColumn", content: children };
}

export function cell(parts: Inline[], header = false): JSONContent {
  return { type: "gzCell", attrs: { header }, content: inlines(parts) };
}

export function table(header: Inline[][], rows: Inline[][][]): JSONContent {
  return {
    type: "gzTable",
    content: [
      { type: "gzRow", content: header.map((parts) => cell(parts, true)) },
      ...rows.map((row) => ({ type: "gzRow", content: row.map((parts) => cell(parts)) })),
    ],
  };
}

export function doc(children: JSONContent[]): JSONContent {
  return { type: "doc", content: children };
}
