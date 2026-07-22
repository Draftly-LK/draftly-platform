export type PartyRole = "transferor" | "transferee" | "lessor" | "lessee" | "mortgagor" | "mortgagee" | "other";

export interface Party {
  id: string;
  role: PartyRole;
  nameToken: string;
  identityDocumentReference?: string;
}

