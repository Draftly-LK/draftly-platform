import type { JSONContent } from "@tiptap/core";
import {
  formField,
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

export const form21Document: JSONContent = {
  type: "doc",
  content: [
    ...formHeader({
      formNumber: "21",
      title: "සහාධිපත්‍ය දේපල ලියාපදිංචි කිරීමේ සාධන පත්‍රය",
      sectionLine: "50 වන වගන්තිය",
    }),
    officeUseBox(),
    ...landParticulars({ includeTransferExtent: false }),
    ...priorRegistration(),
    ...partyBlock("3", "අයදුම්කරු"),
    formSection("4", "ඒකක විස්තර"),
    formField("අ", "ඒකකයේ අංකය :"),
    formField("ආ", "බිම් මහල / මහල :"),
    formField("ඇ", "ප්‍රමාණය :"),
    ...feesBlock("5"),
    lockedBlock("form21-declaration", LEGAL_PLACEHOLDER),
    signatureBlock("අයදුම්කරුගේ අත්සන", "", { layout: "single" }),
    ...witnessesBlock("6", "form21-witnesses"),
  ],
};
