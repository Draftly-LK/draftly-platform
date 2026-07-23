import type { JSONContent } from "@tiptap/core";
import { standardInstrument } from "../_shared-blocks";

export const form09Document: JSONContent = standardInstrument({
  formNumber: "09",
  title: "තබා දීමේ සාධන පත්‍රය",
  sectionLine: "43 වන වගන්තිය",
  party3Title: "තබා දෙන්නා",
  party4Title: "තබා ගන්නා",
  leftSig: "තබා දෙන්නාගේ අත්සන",
  rightSig: "තබා ගන්නාගේ අත්සන",
  blockPrefix: "form09",
  transferExtentLast: true,
});
