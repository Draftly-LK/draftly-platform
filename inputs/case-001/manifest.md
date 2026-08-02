# case-001 — Mawathgama (Homagama) RTA parcel transfers

> **PRIVACY: real client documents.** This folder is gitignored (`inputs/` in
> the repo `.gitignore`) and must NEVER be committed, copied into fixtures,
> demos, screenshots, or the research repo's committed docs. Details below
> exist only to support local extraction testing.

## Case Name

Transfers of two adjacent Bim Saviya title-registered parcels (cadastral map
520005, block 03, parcels 0020 and 0021) at Mawathgama village, GN division
485, Homagama DS division, Colombo district. Land called Katukurunduhena.

## Description

A real RTA (Act No. 21 of 1998) conveyancing bundle covering two parallel
transfer chains over adjacent small parcels (~0.015 ha each). One parcel's
chain runs through a property-development company as an intermediate owner;
the other appears to be a direct transfer between individuals on the
prescribed Form 8. Scanned with CamScanner, Sinhala and English documents
mixed. Ideal v0 test material: title certificate, prescribed instruments,
survey plan extracts, identity, corporate capacity, and payment evidence.

## Transfer Chains (two parallel parcels — flat file layout)

- **Parcel 0020 chain** (title certificate no. ending …090): registered
  Sinhala sale instrument (විකිණීමේ සාධන පත්‍රය, s.43) for parcel 0020
  (`source-005`); vendor company board resolution (dated 2026-07-20)
  authorising onward sale of "Lot 20" to an individual purchaser for
  Rs. 4,590,000 (`source-006`); bank cheque (2026-07-27, Rs. 2,400,000)
  payable to the vendor company — apparent part payment (`source-007`).
  Chain appears to be: individual owner → development company (2025
  registered instrument) → onward sale to purchaser (2026, pending).
- **Parcel 0021 chain** (title certificate no. ending …091): the title
  certificate itself (registered 2025, first class title, with cadastral
  diagram, `source-003`) and Form 8 Instrument of Transfer No. 7347
  (English, notary prepared, 2025-07-14, consideration Rs. 4,819,500) with
  the original stamp-duty receipt as its final page (`source-004`).
- **Whole matter**: a national identity card (old laminated style; which
  party it belongs to is still to be confirmed, `source-001`) and licensed
  surveyor Plan No. 2338 extracts of Lots 17 and 18 (2024 resurvey of the
  same land, local-authority endorsed, `source-002`).

## Folder Meaning

All source documents sit flat in this folder, numbered in review order.

| File | Document type | Chain | Language |
| --- | --- | --- | --- |
| `source-001-national-identity-card.pdf` | National identity card (party identity evidence) | whole matter | Sinhala |
| `source-002-survey-plan-2338-lot-17-18-extracts.pdf` | Licensed surveyor plan extracts, Lots 17 & 18, Plan No. 2338, scale 1:1000 | whole matter | English |
| `source-003-title-certificate-parcel-0021.pdf` | Title certificate (හිමිකම් සහතිකය, s.37) for parcel 0021 with cadastral diagram + folio page | parcel 0021 | Sinhala/Tamil |
| `source-004-form8-instrument-of-transfer-with-stamp-receipt.pdf` | Form 8 Instrument of Transfer No. 7347 (s.43) + stamp-duty receipt (last page) | parcel 0021 | English |
| `source-005-rta-sale-instrument-sinhala-registered.pdf` | Registered RTA sale instrument (s.43) for parcel 0020, with registry endorsements | parcel 0020 | Sinhala |
| `source-006-vendor-board-resolution-lot-20.pdf` | Certified board-resolution extract authorising sale of Lot 20 (corporate capacity/authority) | parcel 0020 | English |
| `source-007-payment-cheque-part-consideration.pdf` | Bank cheque copy — part payment of consideration to vendor company | parcel 0020 | English |

## Notes / open questions (for lawyer verification)

- How surveyor Plan 2338 Lots 17/18 map onto cadastral parcels 0020/0021 is
  not yet established from the documents — a real cross-check target.
- Whose NIC is `source-c01` (transferor, transferee, or another party)?
- The Sinhala instrument's transferee field shows a correction/annotation —
  needs lawyer reading.
- Branch-a onward sale (resolution + cheque, 2026) appears not yet executed
  as an instrument — the missing-documents checklist should catch this.
- Expected red-flag material: date consistency across the chain, extent
  0.0153 vs 0.0159 ha between the two parcels' documents, consideration vs
  cheque amount mismatch (part payment).
- `target_outputs/` not yet created — if the notary's final title report or
  the executed onward transfer becomes available, add it there as ground
  truth.
