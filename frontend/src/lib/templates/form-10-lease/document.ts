import type { JSONContent } from "@tiptap/core";
import { standardInstrument } from "../_shared-blocks";

export const form10Document: JSONContent = standardInstrument({
  formNumber: "10",
  title: "බදු දීමේ සාධන පත්‍රය",
  sectionLine: "43 වන වගන්තිය",
  party3Title: "බදු දෙන්නා",
  party4Title: "බදු ගන්නා",
  leftSig: "බදු දෙන්නාගේ අත්සන",
  rightSig: "බදු ගන්නාගේ අත්සන",
  blockPrefix: "form10",
  transferExtentLast: true,
});
