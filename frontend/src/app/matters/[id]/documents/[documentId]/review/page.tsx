import { DocumentProcessingReviewScreen } from "@/components/matter/document-processing-review-screen";

export default async function ClassificationReviewPage({
  params,
}: {
  params: Promise<{ id: string; documentId: string }>;
}) {
  const { id, documentId } = await params;
  return (
    <DocumentProcessingReviewScreen matterId={id} documentId={documentId} />
  );
}
