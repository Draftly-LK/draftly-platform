import type { JSONContent } from "@tiptap/core";
import { box, column, columns, columnGrid, grid, item, line, signatures, slot, table, type Inline } from "../builders";

/*
 * Blocks that recur across the English edition of Gazette 1886/58. Every
 * string is copied verbatim from the transcriptions in
 * `docs/reference/forms/transcriptions/en/`; the parameters exist only where
 * the printed forms themselves differ, so nothing here harmonises two forms.
 *
 * Slot ids are the same as in the Sinhala templates, so a value keyed by slot
 * id means the same blank in either edition.
 */

const DOTS_SHORT = "...........................................";
const DOTS_LONG = "..........................................................";

/** Opening lines: form number, title, Act, and the section relied on. */
export function formHeader(formNumber: string, title: string): JSONContent[] {
  return [
    line("formNumber", [`Form No. ${formNumber}`], { align: "end" }),
    line("title", [title], { align: "center" }),
    line("act", ["REGISTRATION OF TITLE ACT, NO. 21 OF 1998"], { align: "center" }),
    line("sectionRef", ["SECTION 43"], { align: "center" }),
  ];
}

/**
 * The registry's "office use only" box. It is completed by the receiving
 * officer and the Registrar of Titles, so it holds no lawyer blanks. The two
 * forms print it slightly differently, and the options follow the print.
 */
export function officeUseBox(options: {
  /** Form 08 prints the fee lines with no leader; Form 12 prints one. */
  feeLeaders: boolean;
  /** Form 08 prints two leaders in the registration column; Form 12 prints none. */
  registrationLeaders: boolean;
  /** Form 08 prints "Date :" alone; Form 12 prints a leader after it. */
  registrarDateLeader: boolean;
}): JSONContent {
  const leader = (value: string) => (options.feeLeaders ? ` ${value}` : "");
  return box([
    line("boxHeader", ["For Office use only"], { align: "center" }),
    columns([
      column([
        line("text", ["RECEIVED"], { align: "center" }),
        grid([line("text", ["Date : " + DOTS_SHORT.slice(0, 25)]), line("text", ["(Date stamp)"], { align: "end" })]),
        line("text", [`Time : ${DOTS_SHORT.slice(0, 24)}`]),
        line("text", [`No. : ${DOTS_SHORT.slice(0, 26)}`]),
        line("text", [`Fees :${DOTS_SHORT.slice(0, 24)}`]),
        line("text", [`(a) Stamp Duty (Receipt No.) :${leader(DOTS_LONG.slice(0, 46))}`], { indent: true }),
        line("text", [`(b) Registration fee (Receipt No.) :${leader(DOTS_LONG.slice(0, 39))}`], { indent: true }),
        line("text", [`Certificate of Title No. : ${DOTS_SHORT.slice(0, 28)}`]),
        line("text", [DOTS_SHORT.slice(0, 37)], { align: "end" }),
        line("text", ["Receiving Officer"], { align: "end" }),
      ]),
      column([
        line("text", ["REGISTRATION"], { align: "center" }),
        line("text", ["Registered in the Title"]),
        line("text", [`Register No. ${DOTS_SHORT.slice(0, 26)}`]),
        ...(options.registrationLeaders
          ? [line("text", [DOTS_SHORT.slice(0, 33)]), line("text", [DOTS_SHORT.slice(0, 33)])]
          : [line("text", [""])]),
        line("text", [DOTS_SHORT.slice(0, 39)], { align: "end" }),
        line("text", ["Registrar of Titles"], { align: "end" }),
        line("text", [options.registrarDateLeader ? `Date : ${DOTS_SHORT.slice(0, 22)}` : "Date :"], { indent: true }),
      ]),
    ]),
  ]);
}

/**
 * Item 1. The first ten particulars are printed identically on both forms;
 * (k) and (l) differ in wording, so the caller supplies them. The page prints
 * two columns, (a)-(f) beside (g)-(l), and the entries fill down each column.
 * Ids follow the Sinhala templates: a, aa, ae, aee, i, ii are (a)-(f) and
 * u, uu, e, ee, o, oo are (g)-(l).
 */
export function landDetails(
  prefix: string,
  title: string,
  fields: Record<string, string>,
  last: [JSONContent, JSONContent],
): JSONContent {
  const entry = (id: string, caption: string) =>
    line("entry", [caption, slot(`${prefix}.1.${id}`, { field: fields[id] })]);
  return item("1.", [
    line("itemTitle", [title]),
    columnGrid(
      [
        entry("a", "(a) District : "),
        entry("aa", "(b) Divisional Secretary’s Division : "),
        entry("ae", "(c) Grama Niladhari Division : "),
        entry("aee", "(d) Village or Town : "),
        entry("i", "(e) Street : "),
        entry("ii", "(f) Assessment No. : "),
        entry("u", "(g) Cadastral Map No. : "),
        entry("uu", "(h) Block No. : "),
        entry("e", "(i) Parcel No. : "),
        entry("ee", "(j) Extent : "),
        ...last,
      ],
      6,
    ),
  ]);
}

/** Item 2 — the prior registration reference. Identical on both forms. */
export function priorRegistration(prefix: string, fields: Record<string, string>): JSONContent {
  const entry = (id: string, caption: string) =>
    line("entry", [caption, slot(`${prefix}.2.${id}`, { field: fields[id] })]);
  return item("2.", [
    line("itemTitle", ["Prior Registration Reference :"]),
    entry("a", "(a) Place of Registration : "),
    entry("aa", "(b) Title Certificate No. : "),
    entry("ae", "(c) Class of Title : "),
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
    line("entry", ["(a) Full Name : ", slot(`${id}.a`, { field: fields.name })]),
    line("entry", ["(b) National Identity Card No. : ", slot(`${id}.aa`, { field: fields.nic })]),
    line("entry", ["(c) Address : ", slot(`${id}.ae`, { field: fields.address, multiline: true })]),
  ]);
}

/** The fees item. Form 12 prints "Rs." after each caption; Form 08 does not. */
export function fees(prefix: string, number: string, options: { rupees: boolean }): JSONContent {
  const id = `${prefix}.${number.replace(".", "")}`;
  const rs = options.rupees ? "Rs. " : "";
  return item(number, [
    line("itemTitle", ["Fees :"]),
    grid([
      line("entry", [`(a) Registration Fee : ${rs}`, slot(`${id}.a`)]),
      line("entry", ["Receipt No. : ", slot(`${id}.aa`)]),
      line("entry", [`(b) Stamp duty : ${rs}`, slot(`${id}.ae`)]),
      line("entry", ["Receipt No. : ", slot(`${id}.aee`)]),
    ]),
  ]);
}

/** Witness statement table. The signature column is signed in ink. */
export function witnessTable(prefix: string): JSONContent {
  const header: Inline[][] = [["Full Names of witnesses"], ["N.I.C. No."], ["Address"], ["Signature"]];
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
    line("centerHeading", ["Attestation"], { align: "center", space: true }),
    line(
      "para",
      [
        "Stakeholders and Witnesses shall place their signatures in the presence of their respective attestors and the Notary Public shall certify the ‘Instrument’ only after examining the particulars stipulated in under Section 44 of the Title Registration Act, No. 21 of 1998.",
      ],
      { indent: true },
    ),
    signatures([
      line("signature", ["Date : ", slot(`${prefix}.attestation.date`, { field: fields.date })], {
        space: true,
      }),
      line("signature", [DOTS_LONG], { space: true }),
      line("signature", [""]),
      line("signature", ["Notary Public."], { align: "center" }),
      line("signature", [""]),
      line("signature", ["(Signature and Official Frank)"], { align: "center" }),
    ]),
  ];
}

export const SIGNATURE_DOTS = DOTS_LONG;
