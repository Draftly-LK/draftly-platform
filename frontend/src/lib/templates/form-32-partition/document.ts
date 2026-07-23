import type { JSONContent } from "@tiptap/core";
import {
  emptyTable,
  formSection,
  lockedBlock,
  signatureBlock,
} from "../_helpers";
import {
  formHeader,
  landParticulars,
  officeUseBox,
  priorRegistration,
  partyBlock,
  feesBlock,
  witnessesBlock,
  LEGAL_PLACEHOLDER,
} from "../_shared-blocks";

export const form32Document: JSONContent = {
  type: "doc",
  content: [
    ...formHeader({
      formNumber: "32",
      title: "ඉඩම් බෙදාහැරීමේ අයදුම්පත",
      sectionLine: "43 වන වගන්තිය",
    }),
    officeUseBox(),
    ...landParticulars({ includeTransferExtent: false }),
    ...priorRegistration(),
    ...partyBlock("3", "අයදුම්කරු"),
    formSection("4", "සම-හිමිකරුවන්"),
    emptyTable(["සම්පූර්ණ නම", "ජාතික හැඳුනුම්පත් අංකය", "ලිපිනය", "කොටස"], 3),
    ...feesBlock("5"),
    lockedBlock("form32-declaration", LEGAL_PLACEHOLDER),
    signatureBlock("අයදුම්කරුගේ අත්සන", "", { layout: "single" }),
    ...witnessesBlock("6", "form32-witnesses"),
  ],
};
