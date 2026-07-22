export type ObligationStatus = "upcoming" | "due" | "overdue" | "complete";
export interface Obligation {
  id: string;
  matterId: string;
  labelKey: string;
  dueDate: string;
  status: ObligationStatus;
}
