import { FactsScreen } from "@/components/matter/facts-screen";
export default async function FactsPage({ params }: { params: Promise<{ id: string }> }) { const { id } = await params; return <FactsScreen matterId={id} />; }

