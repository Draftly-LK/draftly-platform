import type { JSONContent } from "@tiptap/core";
import { standardInstrument } from "../_shared-blocks";

export const form11Document: JSONContent = standardInstrument({
  formNumber: "11",
  title: "කැවියට් තැබීමේ සාධන පත්‍රය",
  sectionLine: "43 වන වගන්තිය",
  party3Title: "කැවියට් තබන්නා",
  party4Title: "හිමිකරු",
  leftSig: "කැවියට් තබන්නාගේ අත්සන",
  rightSig: "හිමිකරුගේ අත්සන",
  blockPrefix: "form11",
  transferExtentLast: true,
});
