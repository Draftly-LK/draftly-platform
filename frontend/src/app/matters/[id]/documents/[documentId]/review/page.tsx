import { ClassificationReviewScreen } from "@/components/matter/classification-review-screen";

export default async function ClassificationReviewPage({
  params,
}: {
  params: Promise<{ id: string; documentId: string }>;
}) {
  const { id, documentId } = await params;
  return <ClassificationReviewScreen matterId={id} documentId={documentId} />;
}
