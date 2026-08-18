import { ExportsScreen } from "@/components/matter/exports-screen";

export default async function ExportsPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  return <ExportsScreen matterId={id} />;
}
