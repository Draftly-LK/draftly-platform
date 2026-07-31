import { useDemoStore } from "./demo-store";
import { processDocument, isMockPipelineEnabled } from "@/lib/api/documents";
import type { ProcessDocumentResponse } from "@/lib/api/documents";

const timers = new Map<string, ReturnType<typeof setTimeout>[]>();
const pendingFiles = new Map<string, File>();
const waitQueue: string[] = [];
let activeCount = 0;
const MAX_CONCURRENT = 1;

export function queueDocumentFile(documentId: string, file: File) {
  pendingFiles.set(documentId, file);
}

// TODO(api): POST /api/matters/{matterId}/documents/{documentId}/process
export function simulateDocumentProcessing(
  documentId: string,
  outcome: "ready" | "failed" = "ready",
) {
  stopDocumentProcessing(documentId);
  const file = pendingFiles.get(documentId);

  if (file && !isMockPipelineEnabled()) {
    enqueueRealPipeline(documentId);
    return;
  }

  const first = setTimeout(
    () =>
      useDemoStore
        .getState()
        .setDocumentProcessingState(documentId, "extracting", 0.48),
    900,
  );
  const second = setTimeout(() => {
    if (outcome === "failed") {
      useDemoStore
        .getState()
        .setDocumentProcessingState(documentId, "failed", 0.31);
      return;
    }
    useDemoStore.getState().completeDocumentExtraction(documentId);
  }, 2400);
  timers.set(documentId, [first, second]);
}

function enqueueRealPipeline(documentId: string) {
  if (!waitQueue.includes(documentId)) waitQueue.push(documentId);
  useDemoStore
    .getState()
    .setDocumentProcessingState(documentId, "extracting", 0.25);
  void pumpQueue();
}

async function pumpQueue() {
  while (activeCount < MAX_CONCURRENT && waitQueue.length > 0) {
    const documentId = waitQueue.shift();
    if (!documentId) return;
    const file = pendingFiles.get(documentId);
    if (!file) continue;
    activeCount += 1;
    void runRealPipeline(documentId, file).finally(() => {
      activeCount -= 1;
      void pumpQueue();
    });
  }
}

async function runRealPipeline(documentId: string, file: File) {
  useDemoStore
    .getState()
    .setDocumentProcessingState(documentId, "extracting", 0.4);
  try {
    const result: ProcessDocumentResponse = await processDocument(file);
    useDemoStore.getState().applyDocumentPipelineResult(documentId, result);
  } catch (error) {
    console.error("Document pipeline failed", error);
    useDemoStore
      .getState()
      .setDocumentProcessingState(documentId, "failed", 0.2);
  } finally {
    pendingFiles.delete(documentId);
  }
}

export function stopDocumentProcessing(documentId: string) {
  // TODO(api): DELETE /api/matters/{matterId}/documents/{documentId}/process
  timers.get(documentId)?.forEach((timer) => clearTimeout(timer));
  timers.delete(documentId);
  const queuedIndex = waitQueue.indexOf(documentId);
  if (queuedIndex >= 0) waitQueue.splice(queuedIndex, 1);
}
