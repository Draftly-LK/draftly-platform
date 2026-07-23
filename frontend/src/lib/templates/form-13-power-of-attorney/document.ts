import type { JSONContent } from "@tiptap/core";
import { standardInstrument } from "../_shared-blocks";

export const form13Document: JSONContent = standardInstrument({
  formNumber: "13",
  title: "බලය පැවරීමේ සාධන පත්‍රය",
  sectionLine: "43 වන වගන්තිය",
  party3Title: "බලය පවරන්නා",
  party4Title: "නියෝජිතයා",
  leftSig: "බලය පවරන්නාගේ අත්සන",
  rightSig: "නියෝජිතයාගේ අත්සන",
  blockPrefix: "form13",
  transferExtentLast: true,
});
