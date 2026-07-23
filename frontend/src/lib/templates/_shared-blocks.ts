import type { JSONContent } from "@tiptap/core";
import {
  emptyTable,
  formField,
  formFieldGrid,
  formSection,
  heading,
  lockedBlock,
  paragraph,
  signatureBlock,
} from "./_helpers";

export const LEGAL_PLACEHOLDER = "PLACEHOLDER — legal wording pending lawyer";

export function formHeader(opts: {
  formNumber: string;
  title: string;
  actLine?: string;
  sectionLine?: string;
}): JSONContent[] {
  return [
    paragraph(`ආකෘති පත්‍ර අංක - ${opts.formNumber}`),
    heading(1, opts.title),
    paragraph(opts.actLine ?? "1998 අංක 21 දරන හිමිකම් ලියාපදිංචි කිරීමේ පනත"),
    paragraph(opts.sectionLine ?? "43 වන වගන්තිය"),
  ];
}

export function officeUseBox(): JSONContent {
  return {
    type: "officeUseBox",
    attrs: { heading: "කාර්යාලීය ප්‍රයෝජනය සඳහා පමණි" },
    content: [
      {
        type: "officeUseColumn",
        attrs: { title: "ලැබුණා" },
        content: [
          formField(null, "දිනය :"),
          formField(null, "වේලාව :"),
          formField(null, "අංකය :"),
          formField(null, "ගාස්තු :"),
          formField("අ", "මුද්දර ගාස්තු (ලදුපත් අංකය) :"),
          formField("ආ", "ලියාපදිංචි කිරීමේ ගාස්තු (ලදුපත් අංකය) :"),
          formField(null, "හිමිකම් සහතිකයේ අංකය :"),
          signatureBlock("භාරගත් නිලධාරියා", "", {
            layout: "single",
            showDate: false,
          }),
        ],
      },
      {
        type: "officeUseColumn",
        attrs: { title: "ලියාපදිංචි කිරීම" },
        content: [
          paragraph("දින මුද්‍රාව"),
          paragraph(
            ".................................................. දරන හිමිකම් ලේඛනයේ ලියාපදිංචි කරන ලදී.",
          ),
          signatureBlock("හිමිකම් පිළිබඳ රෙජිස්ට්‍රාර්", "", {
            layout: "single",
            showDate: false,
          }),
          formField(null, "දිනය :"),
        ],
      },
    ],
  };
}

export function landParticulars(opts?: {
  sectionTitle?: string;
  includeTransferExtent?: boolean;
  transferExtentLast?: boolean;
}): JSONContent[] {
  const title = opts?.sectionTitle ?? "ඉඩම පිළිබඳ විස්තර";
  const fields = [
    formField("අ", "දිස්ත්‍රික්කය :"),
    formField("ආ", "ප්‍රාදේශීය ලේකම් කොට්ඨාසය :"),
    formField("ඇ", "ග්‍රාම නිලධාරී කොට්ඨාසය :"),
    formField("ඈ", "ග්‍රාමය හෝ නගරය :"),
    formField("ඉ", "වීදිය :"),
    formField("ඊ", "වරිපනම් අංකය :"),
    formField("උ", "කැඩැස්තර සිතියමේ අංකය :"),
    formField("ඌ", "කලාප අංකය :"),
    formField("එ", "ඉඩම් කොටසේ අංකය :"),
    formField("ඒ", "ප්‍රමාණය :"),
  ];
  if (opts?.includeTransferExtent !== false) {
    if (opts?.transferExtentLast) {
      fields.push(formField("ඔ", "සහාධිපත්‍ය දේපලක් නම් ඒකකයේ අංකය :"));
      fields.push(formField("ඕ", "පැවරීමට යටත් වන ඉඩමේ ප්‍රමාණය :"));
    } else {
      fields.push(formField("ඔ", "පැවරීමට යටත්වන ඉඩමේ ප්‍රමාණය :"));
      fields.push(formField("ඕ", "සහාධිපත්‍ය දේපලක් නම් ඒකකයේ අංකය :"));
    }
  } else {
    fields.push(formField("ඔ", "සහාධිපත්‍ය දේපලක් නම් ඒකකයේ අංකය :"));
  }
  return [formSection("1", title), formFieldGrid(fields)];
}

export function priorRegistration(sectionNumber = "2"): JSONContent[] {
  return [
    formSection(sectionNumber, "පූර්ව ලියාපදිංචියෙහි යොමුව"),
    formField("අ", "ලියාපදිංචි කළ ස්ථානය :"),
    formField("ආ", "හිමිකම් සහතිකයේ අංකය :"),
    formField("ඇ", "හිමිකම් පන්තිය :"),
  ];
}

export function partyBlock(
  number: string,
  title: string,
  demo?: { name?: string; nic?: string; address?: string },
): JSONContent[] {
  return [
    formSection(number, title),
    formField("අ", "සම්පූර්ණ නම :", demo?.name ?? ""),
    formField("ආ", "ජාතික හැඳුනුම්පත් අංකය :", demo?.nic ?? ""),
    formField("ඇ", "ලිපිනය :", demo?.address ?? ""),
  ];
}

export function considerationBlock(number = "5"): JSONContent[] {
  return [
    formSection(number, "ප්‍රතිෂ්ඨාව"),
    formField("අ", "රු. (ඉලක්කමෙන්) :"),
    formField("ආ", "රු. (අකුරෙන්) :"),
  ];
}

export function feesBlock(number = "6"): JSONContent[] {
  return [
    formSection(number, "ගාස්තු"),
    formField("අ", "ලියාපදිංචි කිරීමේ ගාස්තු : රු."),
    formField("ආ", "ලදුපත් අංකය :"),
    formField("ඇ", "මුද්දර ගාස්තු : රු."),
    formField("ඈ", "ලදුපත් අංකය :"),
  ];
}

export function conditionsBlock(number = "7"): JSONContent[] {
  return [formSection(number, "කොන්දේසි"), paragraph(""), paragraph("")];
}

export function encumbrancesBlock(number = "8"): JSONContent[] {
  return [
    formSection(number, "බැඳීම් / වෙනත් ඉඩම් විෂයෙහි ඇති අයිතිය"),
    emptyTable(["ස්වභාවය", "විස්තරය", "වලංගු කාල සීමාව"], 2),
    paragraph("නොගැලපෙන වචන කපා හරින්න."),
  ];
}

export function declarationAndSignatures(opts: {
  blockId: string;
  leftSig: string;
  rightSig: string;
}): JSONContent[] {
  return [
    lockedBlock(opts.blockId, LEGAL_PLACEHOLDER),
    signatureBlock(opts.leftSig, opts.rightSig),
  ];
}

export function lifeInterestBlock(blockId: string): JSONContent[] {
  return [
    lockedBlock(blockId, LEGAL_PLACEHOLDER),
    signatureBlock("ජීවිත භුක්ති හිමිකරුගේ අත්සන", "", { layout: "single" }),
  ];
}

export function witnessesBlock(
  number = "9",
  blockId = "witnesses",
): JSONContent[] {
  return [
    formSection(number, "සාක්ෂිකරුවන්ගේ ප්‍රකාශය"),
    lockedBlock(blockId, LEGAL_PLACEHOLDER),
    emptyTable(
      [
        "සාක්ෂිකරුවන්ගේ සම්පූර්ණ නම",
        "ජාතික හැඳුනුම්පත් අංකය",
        "ලිපිනය",
        "අත්සන",
      ],
      2,
    ),
  ];
}

/** Standard instrument layout shared by Forms 08–13, 23–24, 27–30, etc. */
export function standardInstrument(opts: {
  formNumber: string;
  title: string;
  sectionLine?: string;
  party3Title: string;
  party4Title: string;
  leftSig: string;
  rightSig: string;
  blockPrefix: string;
  transferExtentLast?: boolean;
  extraAfterPrior?: JSONContent[];
}): JSONContent {
  return {
    type: "doc",
    content: [
      ...formHeader({
        formNumber: opts.formNumber,
        title: opts.title,
        sectionLine: opts.sectionLine,
      }),
      officeUseBox(),
      ...landParticulars({ transferExtentLast: opts.transferExtentLast }),
      ...priorRegistration(),
      ...(opts.extraAfterPrior ?? []),
      ...partyBlock("3", opts.party3Title),
      ...partyBlock("4", opts.party4Title),
      ...considerationBlock("5"),
      ...feesBlock("6"),
      ...conditionsBlock("7"),
      ...encumbrancesBlock("8"),
      ...declarationAndSignatures({
        blockId: `${opts.blockPrefix}-declaration`,
        leftSig: opts.leftSig,
        rightSig: opts.rightSig,
      }),
      ...lifeInterestBlock(`${opts.blockPrefix}-life-interest`),
      ...witnessesBlock("9", `${opts.blockPrefix}-witnesses`),
    ],
  };
}
