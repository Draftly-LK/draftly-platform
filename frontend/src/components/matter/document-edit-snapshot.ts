import type { ApiDetectedDocument, ApiDocumentInbox } from "@/types/rta";

/** Only the originals and groups the lawyer is editing participate in renewal. */
export function editSnapshot(
  inbox: ApiDocumentInbox | null,
  sourceIds: string[],
) {
  const ids = [...new Set(sourceIds)].sort();
  return JSON.stringify(
    ids.map((id) => ({
      source: inbox?.sourceFiles.find((source) => source.id === id) ?? null,
      accounting:
        inbox?.pageAccounting?.find((page) => page.sourceFileId === id) ?? null,
      documents:
        inbox?.documents
          .filter((document) =>
            document.fragments.some((fragment) => fragment.sourceFileId === id),
          )
          .sort((a, b) => a.id.localeCompare(b.id))
          .map(documentSnapshot) ?? [],
    })),
  );
}

export function documentSnapshot(document: ApiDetectedDocument) {
  return JSON.stringify({
    id: document.id,
    matterId: document.matterId,
    version: document.version,
    generation: document.interpretationGeneration,
    classId: document.classId,
    classStatus: document.classStatus,
    boundaryStatus: document.boundaryStatus,
    extractionState: document.extractionState,
    relationship: document.versionRelationship,
    fragments: document.fragments,
  });
}
