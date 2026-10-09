import { ChecksScreen } from "@/components/checks/checks-screen";
export default async function ChecksPage({
  params,
  searchParams,
}: {
  params: Promise<{ id: string }>;
  searchParams: Promise<{ requirement?: string | string[] }>;
}) {
  const { id } = await params;
  const { requirement } = await searchParams;
  return (
    <ChecksScreen
      matterId={id}
      targetRequirementId={
        typeof requirement === "string" ? requirement : undefined
      }
    />
  );
}
