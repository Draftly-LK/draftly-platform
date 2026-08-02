import { DocumentsScreen } from "@/components/matter/documents-screen";
export default async function DocumentsPage({ params }: { params: Promise<{ id: string }> }) { const { id } = await params; return <DocumentsScreen matterId={id} />; }

