import { OverviewScreen } from "@/components/matter/overview-screen";
export default async function MatterPage({ params }: { params: Promise<{ id: string }> }) { const { id } = await params; return <OverviewScreen matterId={id} />; }

