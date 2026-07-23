import type { JSONContent } from "@tiptap/core";
import {
  emptyTable,
  formField,
  formSection,
  lockedBlock,
  paragraph,
  signatureBlock,
} from "../_helpers";
import {
  formHeader,
  landParticulars,
  officeUseBox,
  witnessesBlock,
  LEGAL_PLACEHOLDER,
} from "../_shared-blocks";

export const form07Document: JSONContent = {
  type: "doc",
  content: [
    ...formHeader({
      formNumber: "07",
      title: "ඉඩමක් ඒකාබද්ධ කිරීම / අතුරු බෙදීම සඳහා ඉල්ලීම",
      sectionLine: "36 වන වගන්තිය",
    }),
    officeUseBox(),
    paragraph(
      "(ලියාපදිංචි හිමිකරු/හිමිකරුවන් විසින් දෙපිටපතින් පුරවා යැවිය යුතුය.)",
    ),
    paragraph("හිමිකම් පිළිබඳ රෙජිස්ට්‍රාර් වෙත,"),
    formField(null, "දිස්ත්‍රික්කය :"),
    emptyTable(
      [
        "අයිතිකරුගේ/අයිතිකරුවන්ගේ නම/නම්",
        "ජාතික හැඳුනුම්පත් අංකය",
        "ලිපිනය/ලිපිනයන්",
      ],
      3,
    ),
    ...landParticulars({
      sectionTitle: "ඒකාබද්ධ කිරීමට / අතුරු බෙදීමට යෝජිත ඉඩම පිළිබඳ විස්තර",
      includeTransferExtent: false,
    }),
    formSection("2", "පූර්ව ලියාපදිංචියෙහි යොමුව"),
    formField("අ", "ලියාපදිංචි කළ ස්ථානය :"),
    formField("ආ", "හිමිකම් සහතිකයේ අංකය/අංක :"),
    formField("ඇ", "ඉඩමේ ප්‍රමාණය :"),
    lockedBlock("form07-declaration", LEGAL_PLACEHOLDER),
    signatureBlock("අයදුම්කරුගේ අත්සන", "", { layout: "single" }),
    ...witnessesBlock("3", "form07-witnesses"),
  ],
};
