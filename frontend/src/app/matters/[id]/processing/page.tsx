import { ProcessingScreen } from "@/components/matter/processing-screen";

export default async function ProcessingPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return <ProcessingScreen matterId={id} />;
}
