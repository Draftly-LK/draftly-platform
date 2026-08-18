import { MissingDocumentsScreen } from "@/components/matter/missing-documents-screen";
export default async function MissingDocumentsPage({ params }: { params: Promise<{ id: string }> }) { const { id } = await params; return <MissingDocumentsScreen matterId={id} />; }
