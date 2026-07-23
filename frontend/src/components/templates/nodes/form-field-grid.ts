import { Node, mergeAttributes } from "@tiptap/core";

export const FormFieldGrid = Node.create({
  name: "formFieldGrid",
  group: "block",
  content: "formField+",
  defining: true,
  parseHTML() {
    return [{ tag: "div[data-form-field-grid]" }];
  },
  renderHTML({ HTMLAttributes }) {
    return [
      "div",
      mergeAttributes(HTMLAttributes, {
        "data-form-field-grid": "",
        class: "form-field-grid",
      }),
      0,
    ];
  },
});
