import type { JSONContent } from "@tiptap/core";
import { standardInstrument } from "../_shared-blocks";

export const form12Document: JSONContent = standardInstrument({
  formNumber: "12",
  title: "කැවියට් අවලංගු කිරීමේ සාධන පත්‍රය",
  sectionLine: "43 වන වගන්තිය",
  party3Title: "කැවියට් තබන්නා",
  party4Title: "හිමිකරු",
  leftSig: "කැවියට් තබන්නාගේ අත්සන",
  rightSig: "හිමිකරුගේ අත්සන",
  blockPrefix: "form12",
  transferExtentLast: true,
});
