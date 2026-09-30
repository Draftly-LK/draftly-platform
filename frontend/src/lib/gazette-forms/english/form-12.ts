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
 * Form 12 — Cancellation of Mortgage (RTA s. 43), English edition.
 * Source: Gazette Extraordinary 1886/58 of 2014.10.31, pages 14A–15A.
 * Transcription: docs/reference/forms/transcriptions/en/form-12.txt.
 *
 * Wording is verbatim. In this edition the release clause has the mortgagee
 * discharge the land belonging to the mortgagor; the Sinhala edition names the
 * mortgagor as the releasing party. Neither is reconciled here: legal wording
 * is human-owned, and this template is an unapproved transcription.
 */

const P = "f12";

export const form12Document: JSONContent = doc([
  ...formHeader("12", "CANCELLATION OF MORTGAGE"),
  officeUseBox({ feeLeaders: true, registrationLeaders: false, registrarDateLeader: true }),
  landDetails(
    P,
    "Particulars of Land :",
    {
      a: "district",
      aa: "ds_division",
      ae: "gn_division",
      u: "cadastral_map_no",
      uu: "block_no",
      e: "parcel_no",
      ee: "extent",
    },
    [
      line("entry", ["(k) Extent of land subject to mortgage : ", slot(`${P}.1.o`)]),
      line("entry", ["(l) No. of the unit, if condominium property :", slot(`${P}.1.oo`)]),
    ],
  ),
  priorRegistration(P, { a: "place_of_registration", aa: "title_certificate_no", ae: "class_of_title" }),
  party(P, "3.", "Mortgagor :", { name: "registered_owner_name" }),
  party(P, "4.", "Mortgagee :", { name: "mortgagee_name", address: "mortgagee_address" }),
  item("5.", [
    line("itemTitle", ["Instrument of Mortgage :"]),
    table(
      [["Day book number"], ["Date"], ["Principal Amount"], ["Attester"]],
      [
        [
          [slot(`${P}.5.day_book`, { field: "mortgage_reference", labelKey: "mortgageDayBook" })],
          [slot(`${P}.5.date`, { field: "mortgage_registration_date", labelKey: "mortgageDate" })],
          [slot(`${P}.5.principal`, { labelKey: "mortgagePrincipal" })],
          [slot(`${P}.5.attested_by`, { multiline: true, labelKey: "mortgageAttestedBy" })],
        ],
      ],
    ),
  ]),
  fees(P, "6.", { rupees: true }),
  line(
    "para",
    [
      "I ",
      slot(`${P}.release.releasor_name`, { size: "lg", labelKey: "releaseReleasorName" }),
      " of ",
      slot(`${P}.release.releasor_address`, { size: "lg", labelKey: "releaseReleasorAddress" }),
      " (mortgagee) hereby discharge the land belonging to ",
      slot(`${P}.release.mortgagor_name`, { size: "md", labelKey: "releaseMortgagorName" }),
      " of ",
      slot(`${P}.release.mortgagor_address`, { size: "md", labelKey: "releaseMortgagorAddress" }),
      " (mortgagor) as the principal and interest in respect of the above mortgage, has completely been paid. It is requested to register this cancellation of mortgage in the Title Register.",
    ],
    { indent: true, space: true },
  ),
  signatures([
    line("signature", [SIGNATURE_DOTS], { space: true }),
    line("signature", [SIGNATURE_DOTS], { space: true }),
    line("signature", ["Signature of the Mortgagor"], { align: "center" }),
    line("signature", ["Signature of the Mortgagee"], { align: "center" }),
    line("signature", ["Date :", slot(`${P}.sign.owner_date`, { labelKey: "mortgagorSignedOn" })], {
      space: true,
    }),
    line("signature", ["Date :", slot(`${P}.sign.mortgagee_date`, { labelKey: "mortgageeSignedOn" })], {
      space: true,
    }),
  ]),
  line(
    "para",
    [
      "7. Declaration of Witnesses : - We certify that this cancellation of mortgage was signed on ",
      slot(`${P}.7.date`, { size: "sm", labelKey: "witnessedOn" }),
      " at ",
      slot(`${P}.7.place`, { size: "md", labelKey: "witnessedAt" }),
      " in our presence and Mortgagor and the Mortgagee are well known to us.",
    ],
    { indent: true, space: true },
  ),
  witnessTable(P),
  ...attestation(P, { date: "attestation_date" }),
]);
