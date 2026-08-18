import { ApprovalScreen } from "@/components/matter/approval-screen";

export default async function ApprovalPage({
  params,
}: {
  params: Promise<{ id: string; draftId: string }>;
}) {
  const { id, draftId } = await params;
  return <ApprovalScreen matterId={id} draftId={draftId} />;
}
