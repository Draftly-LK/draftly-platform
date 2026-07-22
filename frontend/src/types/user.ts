export type Role = "reviewer" | "approver" | "maintainer" | "administrator";

export interface User {
  id: string;
  displayName: string;
  role: Role;
  notaryRegistration: string;
  jurisdiction: string;
}

