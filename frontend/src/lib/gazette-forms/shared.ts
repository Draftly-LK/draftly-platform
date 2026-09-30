import type { JSONContent } from "@tiptap/core";
import { box, column, columns, grid, item, line, signatures, slot, table, type Inline } from "./builders";

/*
 * Blocks that recur across the Gazette 1886/58 instruments. Every string is
 * copied verbatim from the transcriptions in
 * `docs/reference/forms/transcriptions/`; the parameters exist only where the
 * printed forms themselves differ, so nothing here harmonises two forms.
 */

const DOTS_SHORT = "...........................................";
const DOTS_LONG = "..........................................................";

/** Opening lines: form number, title, Act, and the section relied on. */
export function formHeader(formNumber: string, title: string): JSONContent[] {
  return [
    line("formNumber", [`ආකෘති පත්‍ර අංක - ${formNumber}`], { align: "end" }),
    line("title", [title], { align: "center" }),
    line("act", ["1998 අංක 21 දරන හිමිකම් ලියාපදිංචි කිරීමේ පනත"], { align: "center" }),
    line("sectionRef", ["43 වන වගන්තිය"], { align: "center" }),
  ];
}

/**
 * The registry's "office use only" box. It is completed by the receiving
 * officer and the Registrar of Title, so it holds no lawyer blanks.
 */
export function officeUseBox(options: {
  /** Form 8 prints "ලදුපත් අංකය"; Form 12 prints "බැංකු ලදුපත් අංකය". */
  receipt: string;
  /** Form 8 prints a colon after the certificate number caption; Form 12 does not. */
  certificateColon: boolean;
}): JSONContent {
  return box([
    line("boxHeader", ["කාර්යාලීය ප්‍රයෝජනය සඳහා පමණි"]),
    columns([
      column([
        line("text", ["ලැබුණා"], { align: "center" }),
        grid([line("text", ["දිනය :"]), line("text", ["දින මුද්‍රාව"], { align: "end" })]),
        line("text", ["වේලාව :"]),
        line("text", ["අංකය :"]),
        line("text", ["ගාස්තු :"]),
        line("text", [`(අ) මුද්දර ගාස්තු (${options.receipt}) :`]),
        line("text", [`(ආ) ලියාපදිංචි කිරීමේ ගාස්තු (${options.receipt}) :`]),
        line("text", [options.certificateColon ? "හිමිකම් සහතිකයේ අංකය :" : "හිමිකම් සහතිකයේ අංකය"]),
        line("text", [DOTS_SHORT], { align: "end" }),
        line("text", ["භාරගත් නිලධාරියා"], { align: "end" }),
      ]),
      column([
        line("text", [""]),
        line("text", ["ලියාපදිංචි කිරීම"]),
        line("text", [""]),
        line("text", [`${DOTS_LONG} දරන`]),
        line("text", ["හිමිකම් ලේඛනයේ ලියාපදිංචි කරන ලදී."]),
        line("text", [""]),
        line("text", [DOTS_SHORT], { align: "end" }),
        line("text", ["හිමිකම් පිළිබඳ රෙජිස්ට්‍රාර්"]),
        line("text", [`දිනය : ${DOTS_SHORT.slice(0, 30)}`], { indent: true }),
      ]),
    ]),
  ]);
}

/**
 * Item 1. The first ten particulars are printed identically on both forms;
 * (ඔ) and (ඕ) differ in wording and in order, so the caller supplies them.
 */
export function landDetails(
  prefix: string,
  fields: Record<string, string>,
  last: [JSONContent, JSONContent],
): JSONContent {
  const entry = (id: string, caption: string) =>
    line("entry", [caption, slot(`${prefix}.1.${id}`, { field: fields[id] })]);
  return item("1.", [
    line("itemTitle", ["ඉඩම් පිළිබඳ විස්තර :"]),
    grid([
      entry("a", "(අ) දිස්ත්‍රික්කය : "),
      entry("aa", "(ආ) ප්‍රාදේශීය ලේකම් කොට්ඨාසය : "),
      entry("ae", "(ඇ) ග්‍රාම නිලධාරී කොට්ඨාසය : "),
      entry("aee", "(ඈ) ග්‍රාමය හෝ නගරය : "),
      entry("i", "(ඉ) වීදිය : "),
      entry("ii", "(ඊ) වරිපනම් අංකය : "),
      entry("u", "(උ) කැඩැස්තර සිතියමේ අංකය : "),
      entry("uu", "(ඌ) කලාප අංකය : "),
      entry("e", "(එ) ඉඩම් කොටසේ අංකය : "),
      entry("ee", "(ඒ) ප්‍රමාණය : "),
      ...last,
    ]),
  ]);
}

/** Item 2 — the prior registration reference. Identical on both forms. */
export function priorRegistration(prefix: string, fields: Record<string, string>): JSONContent {
  const entry = (id: string, caption: string) =>
    line("entry", [caption, slot(`${prefix}.2.${id}`, { field: fields[id] })]);
  return item("2.", [
    line("itemTitle", ["පූර්ව ලියාපදිංචියෙහි යොමුව :"]),
    entry("a", "(අ) ලියාපදිංචි කළ ස්ථානය : "),
    entry("aa", "(ආ) හිමිකම් සහතිකයේ අංකය : "),
    entry("ae", "(ඇ) හිමිකම් පන්තිය : "),
  ]);
}

/** A party item: full name, NIC, and address. */
export function party(
  prefix: string,
  number: string,
  title: string,
  fields: { name?: string; nic?: string; address?: string },
): JSONContent {
  const id = `${prefix}.${number.replace(".", "")}`;
  return item(number, [
    line("itemTitle", [title]),
    line("entry", ["(අ) සම්පූර්ණ නම : ", slot(`${id}.a`, { field: fields.name })]),
    line("entry", ["(ආ) ජාතික හැඳුනුම්පත් අංකය : ", slot(`${id}.aa`, { field: fields.nic })]),
    line("entry", ["(ඇ) ලිපිනය : ", slot(`${id}.ae`, { field: fields.address, multiline: true })]),
  ]);
}

/** The fees item. `receipt` is the receipt caption as printed on that form. */
export function fees(prefix: string, number: string, receipt: string): JSONContent {
  const id = `${prefix}.${number.replace(".", "")}`;
  return item(number, [
    line("itemTitle", ["ගාස්තු :"]),
    grid([
      line("entry", ["(අ) ලියාපදිංචි කිරීමේ ගාස්තු : රු. ", slot(`${id}.a`)]),
      line("entry", [`(ආ) ${receipt} : `, slot(`${id}.aa`)]),
      line("entry", ["(ඇ) මුද්දර ගාස්තු : රු. ", slot(`${id}.ae`)]),
      line("entry", [`(ඈ) ${receipt}`, slot(`${id}.aee`)]),
    ]),
  ]);
}

/** Witness statement table. The signature column is signed in ink. */
export function witnessTable(prefix: string): JSONContent {
  const header: Inline[][] = [
    ["සාක්ෂිකරුවන්ගේ", { type: "hardBreak" }, "සම්පූර්ණ නම්"],
    ["ජාතික හැඳුනුම්පත්", { type: "hardBreak" }, "අංකය"],
    ["ලිපිනය"],
    ["අත්සන"],
  ];
  return table(header, [
    [
      [slot(`${prefix}.witness.name`, { multiline: true, labelKey: "witnessNames" })],
      [slot(`${prefix}.witness.nic`, { multiline: true, labelKey: "witnessNics" })],
      [slot(`${prefix}.witness.address`, { multiline: true, labelKey: "witnessAddresses" })],
      [],
    ],
  ]);
}

/** The notary's attestation block, printed identically on both forms. */
export function attestation(prefix: string, fields: { date?: string }): JSONContent[] {
  return [
    line("centerHeading", ["සහතික කිරීම"], { align: "center", space: true }),
    line(
      "para",
      [
        "සටහන : පාර්ශවකරුවන් සහ සාක්ෂිකරුවන් ඔවුනොවුන් විසින් සහතික කරන අය ඉදිරියේදී අත්සන් කල යුතු අතර සහතික කරන නොතාරිස් විසින් 1998 අංක 21 දරන හිමිකම් ලියාපදිංචි කිරීමේ පනතේ 44 වන වගන්තියේ සඳහන් කරුණු පරීක්ෂා කිරීමෙන් අනතුරුව සාධන පත්‍රය සහතික කළ යුතු ය.",
      ],
      { indent: true },
    ),
    signatures([
      line("signature", ["දිනය : ", slot(`${prefix}.attestation.date`, { field: fields.date })], {
        space: true,
      }),
      line("signature", [DOTS_LONG], { space: true }),
      line("signature", [""]),
      line("signature", ["ප්‍රසිද්ධ නොතාරිස්,"], { align: "center" }),
      line("signature", [""]),
      line("signature", ["අත්සන හා නිල මුද්‍රාව."], { align: "center" }),
    ]),
  ];
}

export const SIGNATURE_DOTS = DOTS_LONG;
