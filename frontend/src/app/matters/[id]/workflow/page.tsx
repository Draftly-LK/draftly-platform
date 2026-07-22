import { WorkflowScreen } from "@/components/workflow/workflow-screen";
export default async function MatterWorkflowPage({ params }: { params: Promise<{ id: string }> }) { const { id } = await params; return <WorkflowScreen matterId={id} />; }

