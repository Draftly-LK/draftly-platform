import { MatterAssistantScreen } from "@/components/matter/assistant-screen";

export default async function AssistantPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  return <MatterAssistantScreen matterId={id} />;
}
