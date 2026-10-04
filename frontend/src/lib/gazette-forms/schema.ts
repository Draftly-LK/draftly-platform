import { Extension, Node, mergeAttributes } from "@tiptap/core";
import { Plugin, PluginKey } from "@tiptap/pm/state";

/*
 * Tiptap schema for gazette templates. The prescribed wording is ordinary
 * ProseMirror text, so it selects, copies and prints like any document, but
 * `GazetteLock` refuses every transaction that would change the document.
 * Typing, paste, cut, drop, delete, undo, and programmatic commands all end
 * up as document transactions, so none of them can alter the template. Only
 * an explicit template load (`GAZETTE_TEMPLATE_LOAD` meta) may replace it.
 */

export const GAZETTE_TEMPLATE_LOAD = "gazetteTemplateLoad";
export const gazetteLockKey = new PluginKey("gazetteLock");

export const GazetteLock = Extension.create({
  name: "gazetteLock",
  addProseMirrorPlugins() {
    return [
      new Plugin({
        key: gazetteLockKey,
        filterTransaction: (tr) => !tr.docChanged || tr.getMeta(GAZETTE_TEMPLATE_LOAD) === true,
        props: {
          // Refuse before the transaction is even built, so no native input
          // flickers into the page.
          handlePaste: () => true,
          handleDrop: () => true,
          handleTextInput: () => true,
        },
      }),
    ];
  },
});

const LINE_VARIANTS = new Set([
  "formNumber",
  "title",
  "act",
  "sectionRef",
  "boxHeader",
  "text",
  "itemTitle",
  "entry",
  "para",
  "note",
  "centerHeading",
  "signature",
]);

export const GzLine = Node.create({
  name: "gzLine",
  group: "block",
  content: "(text | gzSlot | hardBreak)*",
  marks: "",
  defining: true,
  addAttributes() {
    return {
      variant: { default: "text" },
      align: { default: "start" },
      indent: { default: false },
      space: { default: false },
    };
  },
  parseHTML: () => [{ tag: "p[data-gz-line]" }],
  renderHTML({ node, HTMLAttributes }) {
    const variant = LINE_VARIANTS.has(node.attrs.variant as string) ? node.attrs.variant : "text";
    return [
      "p",
      mergeAttributes(HTMLAttributes, {
        "data-gz-line": variant,
        "data-align": node.attrs.align,
        "data-indent": node.attrs.indent ? "" : undefined,
        "data-space": node.attrs.space ? "" : undefined,
        class: `gz-line gz-${variant}`,
      }),
      0,
    ];
  },
});

export const GzItem = Node.create({
  name: "gzItem",
  group: "block",
  content: "block+",
  addAttributes() {
    return { number: { default: "" } };
  },
  parseHTML: () => [{ tag: "div[data-gz-item]" }],
  renderHTML({ node, HTMLAttributes }) {
    return [
      "div",
      mergeAttributes(HTMLAttributes, { "data-gz-item": "", class: "gz-item" }),
      ["span", { class: "gz-item-number", "aria-hidden": "false" }, String(node.attrs.number)],
      ["div", { class: "gz-item-body" }, 0],
    ];
  },
});

export const GzGrid = Node.create({
  name: "gzGrid",
  group: "block",
  content: "gzLine+",
  addAttributes() {
    return { cols: { default: 2 }, variant: { default: "fields" }, rows: { default: null } };
  },
  parseHTML: () => [{ tag: "div[data-gz-grid]" }],
  renderHTML({ node, HTMLAttributes }) {
    return [
      "div",
      mergeAttributes(HTMLAttributes, {
        "data-gz-grid": node.attrs.variant === "signatures" ? "signatures" : "fields",
        ...(node.attrs.rows ? { "data-gz-flow": "column" } : {}),
        class: "gz-grid",
        style: `--gz-cols: ${Number(node.attrs.cols) || 2}${node.attrs.rows ? `; --gz-rows: ${Number(node.attrs.rows)}` : ""}`,
      }),
      0,
    ];
  },
});

export const GzBox = Node.create({
  name: "gzBox",
  group: "block",
  content: "block+",
  parseHTML: () => [{ tag: "section[data-gz-box]" }],
  renderHTML({ HTMLAttributes }) {
    return ["section", mergeAttributes(HTMLAttributes, { "data-gz-box": "", class: "gz-box" }), 0];
  },
});

export const GzColumns = Node.create({
  name: "gzColumns",
  group: "block",
  content: "gzColumn+",
  parseHTML: () => [{ tag: "div[data-gz-columns]" }],
  renderHTML({ HTMLAttributes }) {
    return ["div", mergeAttributes(HTMLAttributes, { "data-gz-columns": "", class: "gz-columns" }), 0];
  },
});

export const GzColumn = Node.create({
  name: "gzColumn",
  content: "block+",
  parseHTML: () => [{ tag: "div[data-gz-column]" }],
  renderHTML({ HTMLAttributes }) {
    return ["div", mergeAttributes(HTMLAttributes, { "data-gz-column": "", class: "gz-column" }), 0];
  },
});

/*
 * Printed-form tables are replicas of ruled boxes on the page, not data
 * tables: they keep table semantics through ARIA roles but lay out as a CSS
 * grid, so the page's row heights are the printed ones.
 */
export const GzTable = Node.create({
  name: "gzTable",
  group: "block",
  content: "gzRow+",
  parseHTML: () => [{ tag: "div[data-gz-table]" }],
  renderHTML({ node, HTMLAttributes }) {
    const cols = node.firstChild?.childCount ?? 1;
    return [
      "div",
      mergeAttributes(HTMLAttributes, {
        "data-gz-table": "",
        role: "table",
        class: "gz-table",
        style: `--gz-cols: ${cols}`,
      }),
      0,
    ];
  },
});

export const GzRow = Node.create({
  name: "gzRow",
  content: "gzCell+",
  parseHTML: () => [{ tag: "div[data-gz-row]" }],
  renderHTML({ HTMLAttributes }) {
    return ["div", mergeAttributes(HTMLAttributes, { "data-gz-row": "", role: "row", class: "gz-row" }), 0];
  },
});

export const GzCell = Node.create({
  name: "gzCell",
  content: "(text | gzSlot | hardBreak)*",
  marks: "",
  addAttributes() {
    return { header: { default: false } };
  },
  parseHTML: () => [
    { tag: "div[data-gz-cell=header]", attrs: { header: true } },
    { tag: "div[data-gz-cell]" },
  ],
  renderHTML({ node, HTMLAttributes }) {
    return [
      "div",
      mergeAttributes(HTMLAttributes, {
        "data-gz-cell": node.attrs.header ? "header" : "",
        role: node.attrs.header ? "columnheader" : "cell",
        class: "gz-cell",
      }),
      0,
    ];
  },
});

/**
 * A blank on the printed form. An atom: its value is never document text.
 * The editor attaches an interactive node view; this static rendering is what
 * the node serialises to (and what prints if no view is mounted).
 */
export const GzSlot = Node.create({
  name: "gzSlot",
  group: "inline",
  inline: true,
  atom: true,
  selectable: false,
  draggable: false,
  addAttributes() {
    return {
      id: { default: null },
      field: { default: null },
      size: { default: "fill" },
      multiline: { default: false },
      bare: { default: false },
      labelKey: { default: null },
    };
  },
  parseHTML: () => [{ tag: "span[data-gz-slot]" }],
  renderHTML({ node, HTMLAttributes }) {
    return [
      "span",
      mergeAttributes(HTMLAttributes, {
        "data-gz-slot": node.attrs.id,
        "data-size": node.attrs.size,
        class: "gz-slot",
      }),
    ];
  },
});

// A gazette document needs only these three base nodes; StarterKit would add
// headings, lists and marks that a prescribed form never contains.
export const GzDocument = Node.create({ name: "doc", topNode: true, content: "block+" });
export const GzText = Node.create({ name: "text", group: "inline" });
export const GzHardBreak = Node.create({
  name: "hardBreak",
  group: "inline",
  inline: true,
  selectable: false,
  parseHTML: () => [{ tag: "br" }],
  renderHTML: () => ["br"],
});

export const GAZETTE_NODES = [GzDocument, GzText, GzHardBreak, GzLine, GzItem, GzGrid, GzBox, GzColumns, GzColumn, GzTable, GzRow, GzCell];
