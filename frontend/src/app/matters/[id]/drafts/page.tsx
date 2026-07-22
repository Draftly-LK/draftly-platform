import { DraftsScreen } from "@/components/editor/drafts-screen";
export default async function DraftsPage({ params }: { params: Promise<{ id: string }> }) { const { id } = await params; return <DraftsScreen matterId={id} />; }

