import type { JSONContent } from "@tiptap/core";
import { doc, item, line, signatures, slot, table } from "../builders";
import {
  SIGNATURE_DOTS,
  attestation,
  fees,
  formHeader,
  landDetails,
  officeUseBox,
  party,
  priorRegistration,
  witnessTable,
} from "./shared";

/*
 * Form 08 — Instrument of Transfer or Sale (RTA s. 43), English edition.
 * Source: Gazette Extraordinary 1886/58 of 2014.10.31, pages 4A–6A.
 * Transcription: docs/reference/forms/transcriptions/en/form-08.txt.
 *
 * Wording is verbatim, including the gazette's own phrasing ("It is hereby
 * request to register", "was revocated", "stipulated in under"). None of it is
 * corrected here: legal wording is human-owned, and this template is an
 * unapproved transcription.
 */

const P = "f08";

export const form08Document: JSONContent = doc([
  ...formHeader("08", "INSTRUMENT OF TRANSFER OR SALE"),
  officeUseBox({ feeLeaders: false, registrationLeaders: true, registrarDateLeader: false }),
  landDetails(
    P,
    "Particulars of Land Parcel :",
    {
      a: "district",
      aa: "ds_division",
      ae: "gn_division",
      aee: "village",
      ii: "assessment_number",
      u: "cadastral_map_no",
      uu: "block_no",
      e: "parcel_no",
      ee: "extent",
    },
    [
      line("entry", ["(k) Extent transferred : ", slot(`${P}.1.o`, { field: "extent_subject_to_transfer" })]),
      line("entry", ["(l) No. of the parcel, if condominium property ", slot(`${P}.1.oo`)]),
    ],
  ),
  priorRegistration(P, { a: "place_of_registration", aa: "title_certificate_no", ae: "class_of_title" }),
  party(P, "3.", "Transferor :", {
    name: "transferor_name",
    nic: "transferor_nic",
    address: "transferor_address",
  }),
  party(P, "4.", "Transferee :", {
    name: "transferee_name",
    nic: "transferee_nic",
    address: "transferee_address",
  }),
  item("5.", [
    line("itemTitle", ["Consideration :"]),
    line("entry", ["(a) Rs. (in figures) : ", slot(`${P}.5.a`, { field: "consideration" })]),
    line("entry", ["(b) Rs. (in letters) : ", slot(`${P}.5.aa`, { field: "consideration_words" })]),
  ]),
  fees(P, "6.", { rupees: false }),
  item("7.", [line("itemTitle", ["Conditions : ", slot(`${P}.7`, { multiline: true, size: "lg", labelKey: "conditions" })])]),
  item("8.", [
    line("itemTitle", [
      "Encumbrances / Rights over other land : ",
      slot(`${P}.8.other_land`, { size: "lg", labelKey: "encumbranceOtherLand" }),
    ]),
    table(
      [["Nature"], ["Particulars"], ["Validity Period"]],
      [
        [
          [slot(`${P}.8.nature`, { multiline: true, labelKey: "encumbranceNature" })],
          [slot(`${P}.8.details`, { multiline: true, labelKey: "encumbranceDetails" })],
          [slot(`${P}.8.period`, { multiline: true, labelKey: "encumbrancePeriod" })],
        ],
      ],
    ),
  ]),
  line(
    "para",
    [
      "The Transferor for the consideration herein expressed hereby transfers to the Transferee the title to the land parcel, title to the interest herein specified in the land parcel above described, subject to the encumbrances as shown hereon on this ",
      slot(`${P}.transfer.day`, { size: "md", labelKey: "transferDay" }),
      " day of ",
      slot(`${P}.transfer.month`, { size: "md", labelKey: "transferMonth" }),
      " 20",
      slot(`${P}.transfer.year`, { size: "xs", labelKey: "transferYear" }),
      " It is hereby request to register this “Instrument of Transfer” in the Title Register.",
    ],
    { indent: true, space: true },
  ),
  signatures([
    line("signature", [SIGNATURE_DOTS], { space: true }),
    line("signature", [SIGNATURE_DOTS], { space: true }),
    line("signature", ["Signature of the Transferor"], { align: "center" }),
    line("signature", ["Signature of the Transferee"], { align: "center" }),
    line("signature", ["Date : ", slot(`${P}.sign.transferor_date`, { bare: true, labelKey: "transferorSignedOn" })], {
      space: true,
    }),
    line("signature", ["Date : ", slot(`${P}.sign.transferee_date`, { bare: true, labelKey: "transfereeSignedOn" })], {
      space: true,
    }),
  ]),
  line(
    "para",
    [
      "I, ",
      slot(`${P}.life_interest.holder`, { size: "xl", labelKey: "lifeInterestHolder" }),
      " do hereby declare that the life interest pertaining to the land parcel indicated hereto was revocated. (Fill this part if relevant)",
    ],
    { indent: true, space: true },
  ),
  line(
    "para",
    [
      "9. Declaration of Witnesses : - We certify that the instrument of transfer and sale was signed on ",
      slot(`${P}.9.date`, { size: "sm", labelKey: "witnessedOn" }),
      " at ",
      slot(`${P}.9.place`, { size: "md", labelKey: "witnessedAt" }),
      " in our presence and transferor and transferee are well known to us.",
    ],
    { indent: true, space: true },
  ),
  witnessTable(P),
  ...attestation(P, { date: "attestation_date" }),
]);
