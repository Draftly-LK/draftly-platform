import { ActivityScreen } from "@/components/activity/activity-screen";
export default async function ActivityPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  return <ActivityScreen matterId={id} />;
}
