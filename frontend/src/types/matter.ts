import type { Party } from "./party";

export type RegistrationRegime = "rta" | "deed" | "condominium" | "special-area";
export type MatterType = "transfer" | "gift" | "lease" | "mortgage" | "other";
export type MatterStatus = "open" | "in-review" | "blocked" | "ready-to-draft" | "closed";
export type NotarialFunction = "examination" | "drafting" | "execution" | "attestation";

export interface MatterProgress { examination: number; drafting: number; execution: number; attestation: number }

export interface Matter {
  id: string;
  reference: string;
  clientReference?: string;
  regime: RegistrationRegime;
  type: MatterType;
  parties: Party[];
  status: MatterStatus;
  activeFunction: NotarialFunction;
  progress: MatterProgress;
  ownerId: string;
  createdAt: string;
  updatedAt: string;
}

