import type { JSONContent } from "@tiptap/core";

export function text(value: string): JSONContent {
  return { type: "text", text: value };
}

export function paragraph(value?: string): JSONContent {
  return {
    type: "paragraph",
    content: value ? [text(value)] : undefined,
  };
}

export function heading(
  level: 1 | 2 | 3,
  value: string,
  attrs?: Record<string, unknown>,
): JSONContent {
  return {
    type: "heading",
    attrs: { level, ...attrs },
    content: [text(value)],
  };
}

export function formField(
  letter: string | null,
  label: string,
  value = "",
): JSONContent {
  return {
    type: "formField",
    attrs: { letter, label },
    content: value ? [text(value)] : undefined,
  };
}

export function formSection(number: string, title: string): JSONContent {
  return {
    type: "formSection",
    attrs: { number, title },
  };
}

export function formFieldGrid(fields: JSONContent[]): JSONContent {
  return {
    type: "formFieldGrid",
    content: fields,
  };
}

export function lockedBlock(id: string, body: string): JSONContent {
  return {
    type: "lockedBlock",
    attrs: { template_block_id: id },
    content: [paragraph(body)],
  };
}

export function signatureBlock(
  leftLabel: string,
  rightLabel = "",
  options?: { layout?: "pair" | "single"; showDate?: boolean },
): JSONContent {
  return {
    type: "signatureBlock",
    attrs: {
      leftLabel,
      rightLabel,
      layout: options?.layout ?? "pair",
      showDate: options?.showDate ?? true,
    },
  };
}

export function tableHeader(label: string): JSONContent {
  return {
    type: "tableHeader",
    content: [paragraph(label)],
  };
}

export function tableCell(value = ""): JSONContent {
  return {
    type: "tableCell",
    content: [paragraph(value)],
  };
}

export function tableRow(cells: JSONContent[]): JSONContent {
  return {
    type: "tableRow",
    content: cells,
  };
}

export function emptyTable(headers: string[], rows: number): JSONContent {
  return {
    type: "table",
    content: [
      tableRow(headers.map(tableHeader)),
      ...Array.from({ length: rows }, () =>
        tableRow(headers.map(() => tableCell())),
      ),
    ],
  };
}
