import { useDemoStore } from "./demo-store";

const timers = new Map<string, ReturnType<typeof setTimeout>[]>();

// TODO(api): POST /api/matters/{matterId}/documents/{documentId}/process
export function simulateDocumentProcessing(
  documentId: string,
  outcome: "ready" | "failed" = "ready",
) {
  stopDocumentProcessing(documentId);
  const first = setTimeout(
    () =>
      useDemoStore
        .getState()
        .setDocumentProcessingState(documentId, "extracting", 0.48),
    900,
  );
  const second = setTimeout(
    () =>
      useDemoStore
        .getState()
        .setDocumentProcessingState(
          documentId,
          outcome === "ready" ? "ready-for-review" : "failed",
          outcome === "ready" ? 0.88 : 0.31,
        ),
    2400,
  );
  timers.set(documentId, [first, second]);
}

export function stopDocumentProcessing(documentId: string) {
  // TODO(api): DELETE /api/matters/{matterId}/documents/{documentId}/process
  timers.get(documentId)?.forEach((timer) => clearTimeout(timer));
  timers.delete(documentId);
}
