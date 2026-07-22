export type AuditTargetType = "matter" | "document" | "fact" | "check" | "workflow-step" | "answer" | "draft" | "permission";
export interface AuditEvent { id: string; matterId: string; actor: string; action: string; targetType: AuditTargetType; targetId: string; before?: unknown; after?: unknown; timestamp: string }

