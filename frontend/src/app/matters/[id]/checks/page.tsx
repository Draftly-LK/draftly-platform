import { ChecksScreen } from "@/components/checks/checks-screen";
export default async function ChecksPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  return <ChecksScreen matterId={id} />;
}
