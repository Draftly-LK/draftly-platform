import { Node, mergeAttributes } from "@tiptap/core";

function dateLine(): [string, Record<string, string>, ...unknown[]] {
  return [
    "div",
    { class: "signature-date" },
    ["span", {}, "දිනය :"],
    ["span", { class: "signature-date-line" }],
  ];
}

function signatureSlot(label: string, showDate: boolean) {
  const children: unknown[] = [
    ["div", { class: "signature-line" }],
    ["div", { class: "signature-label" }, label],
  ];
  if (showDate) children.push(dateLine());
  return ["div", { class: "signature-slot" }, ...children];
}

export const SignatureBlock = Node.create({
  name: "signatureBlock",
  group: "block",
  atom: true,
  selectable: true,
  addAttributes() {
    return {
      leftLabel: { default: "" },
      rightLabel: { default: "" },
      showDate: { default: true },
      layout: { default: "pair" },
    };
  },
  parseHTML() {
    return [{ tag: "div[data-signature-block]" }];
  },
  renderHTML({ HTMLAttributes, node }) {
    const leftLabel = node.attrs.leftLabel as string;
    const rightLabel = node.attrs.rightLabel as string;
    const showDate = Boolean(node.attrs.showDate);
    const layout = node.attrs.layout as string;
    const attrs = mergeAttributes(HTMLAttributes, {
      "data-signature-block": "",
      class:
        layout === "single"
          ? "signature-block signature-block-single"
          : "signature-block",
    });

    if (layout === "single") {
      return ["div", attrs, signatureSlot(leftLabel, showDate)];
    }

    return [
      "div",
      attrs,
      signatureSlot(leftLabel, showDate),
      signatureSlot(rightLabel, showDate),
    ];
  },
});
