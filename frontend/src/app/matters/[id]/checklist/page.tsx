import { ChecklistScreen } from "@/components/matter/checklist-screen";

export default async function ChecklistPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  return <ChecklistScreen matterId={id} />;
}
