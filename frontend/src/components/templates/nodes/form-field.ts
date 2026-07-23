import { Node, mergeAttributes } from "@tiptap/core";

export const FormField = Node.create({
  name: "formField",
  group: "block",
  content: "inline*",
  defining: true,
  addAttributes() {
    return {
      letter: { default: null },
      label: { default: "" },
    };
  },
  parseHTML() {
    return [{ tag: "div[data-form-field]" }];
  },
  renderHTML({ HTMLAttributes, node }) {
    const letter = node.attrs.letter as string | null;
    const label = node.attrs.label as string;
    const labelText = letter ? `(${letter}) ${label}` : label;
    return [
      "div",
      mergeAttributes(HTMLAttributes, {
        "data-form-field": "",
        class: "form-field",
      }),
      [
        "span",
        { class: "form-field-label", contenteditable: "false" },
        labelText,
      ],
      ["span", { class: "form-field-value" }, 0],
    ];
  },
});
