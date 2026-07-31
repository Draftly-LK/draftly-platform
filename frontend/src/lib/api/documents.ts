import type {
  DocumentKind,
  DocumentRelation,
  IdentityExtractedFields,
  IdentitySide,
} from "@/types";

export type ProcessDocumentResponse = {
  kind: DocumentKind;
  relation: DocumentRelation;
  identity_side: IdentitySide | null;
  extracted_text: string;
  extracted_fields: IdentityExtractedFields | Record<string, string | null>;
  extraction_confidence: number;
  undetected_fields: string[];
  display_name: string | null;
};

function apiBase(): string {
  return (
    process.env.NEXT_PUBLIC_API_BASE_URL?.replace(/\/$/, "") ||
    "http://127.0.0.1:8000"
  );
}

export function isMockPipelineEnabled(): boolean {
  return process.env.NEXT_PUBLIC_USE_MOCK_PIPELINE === "true";
}

// TODO(api): POST /api/documents/process (FastAPI)
export async function processDocument(
  file: File,
): Promise<ProcessDocumentResponse> {
  const form = new FormData();
  form.append("file", file, file.name);
  const response = await fetch(`${apiBase()}/api/documents/process`, {
    method: "POST",
    body: form,
  });
  if (!response.ok) {
    const detail = await response.text();
    throw new Error(detail || `Process failed (${response.status})`);
  }
  return (await response.json()) as ProcessDocumentResponse;
}
