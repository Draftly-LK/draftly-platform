import { Dashboard } from "@/components/home/dashboard";
import { AppShell } from "@/components/shell/app-shell";
import { demoOnly, obligations as obligationFixtures } from "@/lib/mocks";

export function HomeScreen() {
  // Fixture deadlines are demo-only; with the API configured there are none to show.
  const obligations = demoOnly(obligationFixtures);
  return (
    <AppShell>
      <Dashboard obligations={obligations} />
    </AppShell>
  );
}
