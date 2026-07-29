import { DocumentsScreen } from "@/components/matter/documents-screen";

export default async function DocumentsPage({
  params,
  searchParams,
}: {
  params: Promise<{ id: string }>;
  searchParams: Promise<{ pair?: string }>;
}) {
  const { id } = await params;
  const query = await searchParams;
  return <DocumentsScreen matterId={id} openPairing={query.pair === "1"} />;
}
