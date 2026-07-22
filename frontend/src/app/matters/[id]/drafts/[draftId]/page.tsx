import { DraftEditorScreen } from "@/components/editor/draft-editor-screen";
export default async function DraftEditorPage({ params }: { params: Promise<{ id: string; draftId: string }> }) { const { id, draftId } = await params; return <DraftEditorScreen matterId={id} draftId={draftId} />; }

