import type { JSONContent } from "@tiptap/core";
import {
  formField,
  formSection,
  heading,
  lockedBlock,
  paragraph,
  signatureBlock,
  emptyTable,
} from "../_helpers";
import { LEGAL_PLACEHOLDER } from "../_shared-blocks";

export const form19aDocument: JSONContent = {
  type: "doc",
  content: [
    paragraph("ආකෘති පත්‍ර අංක - 19අ"),
    heading(1, "හිමිකම් සහතිකය"),
    paragraph("1998 අංක 21 දරන හිමිකම් ලියාපදිංචි කිරීමේ පනත"),
    paragraph("මුල් ලියාපදිංචිය"),
    formSection("1", "ඉඩම පිළිබඳ විස්තර"),
    formField("අ", "දිස්ත්‍රික්කය :"),
    formField("ආ", "කැඩැස්තර සිතියමේ අංකය :"),
    formField("ඇ", "කලාප අංකය :"),
    formField("ඈ", "ඉඩම් කොටසේ අංකය :"),
    formField("ඉ", "ප්‍රමාණය :"),
    formSection("2", "හිමිකරු"),
    formField("අ", "සම්පූර්ණ නම :"),
    formField("ආ", "ජාතික හැඳුනුම්පත් අංකය :"),
    formField("ඇ", "ලිපිනය :"),
    formField(null, "හිමිකම් පන්තිය :"),
    formSection("3", "බැඳීම්"),
    emptyTable(["ස්වභාවය", "විස්තරය", "වලංගු කාල සීමාව"], 2),
    lockedBlock("form19a-body", LEGAL_PLACEHOLDER),
    signatureBlock("හිමිකම් පිළිබඳ රෙජිස්ට්‍රාර්", "", { layout: "single" }),
  ],
};
