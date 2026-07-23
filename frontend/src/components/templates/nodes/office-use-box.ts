import { Node, mergeAttributes } from "@tiptap/core";

export const OfficeUseColumn = Node.create({
  name: "officeUseColumn",
  content: "block+",
  defining: true,
  addAttributes() {
    return {
      title: { default: "" },
    };
  },
  parseHTML() {
    return [{ tag: "div[data-office-use-column]" }];
  },
  renderHTML({ HTMLAttributes, node }) {
    const title = node.attrs.title as string;
    return [
      "div",
      mergeAttributes(HTMLAttributes, {
        "data-office-use-column": "",
        class: "office-use-column",
      }),
      [
        "div",
        { class: "office-use-column-title", contenteditable: "false" },
        title,
      ],
      ["div", { class: "office-use-column-body" }, 0],
    ];
  },
});

export const OfficeUseBox = Node.create({
  name: "officeUseBox",
  group: "block",
  content: "officeUseColumn{2}",
  defining: true,
  isolating: true,
  addAttributes() {
    return {
      heading: { default: "කාර්යාලීය ප්‍රයෝජනය සඳහා පමණි" },
    };
  },
  parseHTML() {
    return [{ tag: "section[data-office-use-box]" }];
  },
  renderHTML({ HTMLAttributes, node }) {
    const heading = node.attrs.heading as string;
    return [
      "section",
      mergeAttributes(HTMLAttributes, {
        "data-office-use-box": "",
        class: "office-use-box",
      }),
      [
        "div",
        { class: "office-use-heading", contenteditable: "false" },
        heading,
      ],
      ["div", { class: "office-use-columns" }, 0],
    ];
  },
});
