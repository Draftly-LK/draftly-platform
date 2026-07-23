import { Node, mergeAttributes } from "@tiptap/core";

export const FormSection = Node.create({
  name: "formSection",
  group: "block",
  atom: true,
  selectable: true,
  addAttributes() {
    return {
      number: { default: "" },
      title: { default: "" },
    };
  },
  parseHTML() {
    return [{ tag: "h2[data-form-section]" }];
  },
  renderHTML({ HTMLAttributes, node }) {
    const number = (node.attrs.number as string).trim();
    const title = node.attrs.title as string;
    const text = number ? `${number}. ${title}` : title;
    return [
      "h2",
      mergeAttributes(HTMLAttributes, {
        "data-form-section": "",
        class: "form-section-heading",
      }),
      text,
    ];
  },
});
