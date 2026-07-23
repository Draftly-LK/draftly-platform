import type { JSONContent } from "@tiptap/core";
import { standardInstrument } from "../_shared-blocks";

export const form30Document: JSONContent = standardInstrument({
  formNumber: "30",
  title: "බලය පැවරීම අවලංගු කිරීමේ සාධන පත්‍රය",
  sectionLine: "43 වන වගන්තිය",
  party3Title: "බලය පවරන්නා",
  party4Title: "නියෝජිතයා",
  leftSig: "බලය පවරන්නාගේ අත්සන",
  rightSig: "නියෝජිතයාගේ අත්සන",
  blockPrefix: "form30",
  transferExtentLast: false,
});
