import { CaseReaderScreen } from "@/components/library/case-law";

export default async function CaseReaderPage({
  params,
}: {
  params: Promise<{ caseId: string }>;
}) {
  const { caseId } = await params;
  return <CaseReaderScreen caseId={caseId} />;
}
