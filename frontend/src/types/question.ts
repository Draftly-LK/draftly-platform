export interface Question { id: string; prompt: string; scope: "matter" | "step" | "standalone"; language: "en" | "si"; frequentlyWrong: boolean }
export interface QuestionSet { id: string; titleKey: string; descriptionKey: string; questionIds: string[]; approvalState: "draft" | "approved" | "retired"; ownerId: string }

