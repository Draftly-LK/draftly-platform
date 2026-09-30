import type { JSONContent } from "@tiptap/core";
import { doc, grid, item, line, signatures, slot, table } from "./builders";
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
 * Form 08 — Instrument of Transfer or Sale (RTA s. 43).
 * Source: Gazette Extraordinary 1886/58 of 2014.10.31, pages 4A–6A.
 * Transcription: docs/reference/forms/transcriptions/form-08.txt.
 *
 * Wording is verbatim, including the gazette's own spelling variants
 * ("ප්‍රතිශ්ඨාව" in item 5 against "ප්‍රතිෂ්ඨාව" in the transfer clause,
 * "ලේඛණයේ", "වන ම", "ජිවිත"). None of it is corrected here: legal wording is
 * human-owned, and this template is an unapproved transcription.
 */

const P = "f08";

export const form08Document: JSONContent = doc([
  ...formHeader("08", "පැවරීමේ හෝ විකිණීමේ සාධන පත්‍රය"),
  officeUseBox({ receipt: "ලදුපත් අංකය", certificateColon: true }),
  landDetails(
    P,
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
      line("entry", [
        "(ඔ) පැවරීමට යටත්වන ඉඩමේ ප්‍රමාණය : ",
        slot(`${P}.1.o`, { field: "extent_subject_to_transfer" }),
      ]),
      line("entry", ["(ඕ) සහාධිපත්‍ය දේපලක් නම ඒකකයේ අංකය : ", slot(`${P}.1.oo`)]),
    ],
  ),
  priorRegistration(P, { a: "place_of_registration", aa: "title_certificate_no", ae: "class_of_title" }),
  party(P, "3.", "පැවරුම්කරු :", {
    name: "transferor_name",
    nic: "transferor_nic",
    address: "transferor_address",
  }),
  party(P, "4.", "පැවරුම්ලාභී :", {
    name: "transferee_name",
    nic: "transferee_nic",
    address: "transferee_address",
  }),
  item("5.", [
    line("itemTitle", ["ප්‍රතිශ්ඨාව :"]),
    grid([
      line("entry", ["(අ) රු. : ", slot(`${P}.5.a`, { field: "consideration" }), " (ඉලක්කමෙන්)"]),
      line("entry", ["(ආ) රු. ", slot(`${P}.5.aa`, { field: "consideration_words" }), " (අකුරෙන්)"]),
    ]),
  ]),
  fees(P, "6.", "ලදුපත් අංකය"),
  item("7.", [line("itemTitle", ["කොන්දේසි : ", slot(`${P}.7`, { multiline: true, size: "lg", labelKey: "conditions" })])]),
  item("8.", [
    line("itemTitle", ["බැඳීම් / වෙනත් ඉඩම් විෂයෙහි ඇති අයිතිය :"]),
    table(
      [["ස්වභාවය"], ["විස්තරය"], ["වලංගු කාල සීමාව"]],
      [
        [
          [slot(`${P}.8.nature`, { multiline: true, labelKey: "encumbranceNature" })],
          [slot(`${P}.8.details`, { multiline: true, labelKey: "encumbranceDetails" })],
          [slot(`${P}.8.period`, { multiline: true, labelKey: "encumbrancePeriod" })],
        ],
      ],
    ),
    line("note", ["නොගැලපෙන වචන කපා හරින්න."]),
  ]),
  line(
    "para",
    [
      "ඉහත විස්තර කොට ඇති ඉඩම් කොටසේ අයිතිය ඒ ඉඩම් කොටසට පැවරුම්කරු සතු සම්බන්ධතාව, මෙහි දක්වා ඇති බැඳීම්වලට යටත්ව, මෙහි ප්‍රකාශ කොට ඇති ප්‍රතිෂ්ඨාව සඳහා වර්ෂ 20 ",
      slot(`${P}.transfer.year`, { size: "xs", labelKey: "transferYear" }),
      " / ",
      slot(`${P}.transfer.month`, { size: "xs", labelKey: "transferMonth" }),
      " මස ",
      slot(`${P}.transfer.day`, { size: "xs", labelKey: "transferDay" }),
      " වන දින පැවරුම්කරු විසින් පැවරුම්ලාභී වෙත මෙයින් පවරා දෙන ලදී. මෙම විකිණීමේ සාධන පත්‍රය හිමිකම් ලේඛණයේ ලියාපදිංචි කරන මෙන් ඉල්ලමි.",
    ],
    { indent: true, space: true },
  ),
  signatures([
    line("signature", [SIGNATURE_DOTS], { space: true }),
    line("signature", [SIGNATURE_DOTS], { space: true }),
    line("signature", ["පැවරුම්කරුගේ අත්සන"], { align: "center" }),
    line("signature", ["පැවරුම්ලාභියාගේ අත්සන"], { align: "center" }),
    line("signature", ["දිනය : ", slot(`${P}.sign.transferor_date`, { bare: true, labelKey: "transferorSignedOn" })], {
      space: true,
    }),
    line("signature", ["දිනය : ", slot(`${P}.sign.transferee_date`, { bare: true, labelKey: "transfereeSignedOn" })], {
      space: true,
    }),
  ]),
  line(
    "para",
    [
      slot(`${P}.life_interest.holder`, { size: "xl", labelKey: "lifeInterestHolder" }),
      " වන ම විසින් මෙහි සඳහන් ඉඩම් කොටස සම්බන්ධයෙන් තබාගෙන තිබූ ජීවිත භුක්ති බලය අත්හරින ලද බව මෙයින් ප්‍රකාශ කරමි. (මෙම කොටස අදාළ වන්නේ නම් පමණක් සම්පූර්ණ කරන්න.)",
    ],
    { space: true },
  ),
  grid([
    line("signature", [`ජිවිත භුක්ති හිමිකරුගේ අත්සන ${SIGNATURE_DOTS.slice(0, 40)}`], { indent: true, space: true }),
    line("signature", ["දිනය :- ", slot(`${P}.life_interest.date`, { bare: true, size: "sm", labelKey: "lifeInterestSignedOn" })], {
      space: true,
    }),
  ]),
  line(
    "para",
    [
      "9. සාක්ෂිකරුවන්ගේ ප්‍රකාශය : මෙම පැවරුම් සාධන පත්‍රය ",
      slot(`${P}.9.date`, { size: "sm", labelKey: "witnessedOn" }),
      " දින අප ඉදිරියේ ",
      slot(`${P}.9.place`, { size: "md", labelKey: "witnessedAt" }),
      " දී අත්සන් කරන ලද බවත්, පැවරුම්කරු හා පැවරුම්ලාභීන් අප හොඳින් දන්නා හඳුනන අය බවත්, අප මෙයින් සහතික කරමු.",
    ],
    { indent: true, space: true },
  ),
  witnessTable(P),
  ...attestation(P, { date: "attestation_date" }),
]);
