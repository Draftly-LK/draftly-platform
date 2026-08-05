export type Role = "reviewer" | "approver" | "maintainer" | "administrator";

export interface User {
  id: string;
  displayName: string;
  role: Role;
  /** Notary’s code / registration number */
  notaryRegistration: string;
  jurisdiction: string;
  qualifications: string;
  professionalTitles: string;
  addressLine1: string;
  addressLine2: string;
  phone: string;
}
