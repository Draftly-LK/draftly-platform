import { MatterHeader } from "./matter-header";
import { Sidebar } from "./sidebar";

export function AppShell({
  children,
  matterId,
}: {
  children: React.ReactNode;
  matterId?: string;
}) {
  // No separate top bar: the page or matter header is the only bar above the
  // content, and the account menu lives in the sidebar footer.
  return (
    <div className="bg-canvas min-h-screen">
      <Sidebar />
      <div className="min-w-0 md:pl-[var(--sidebar-width)]">
        {matterId && <MatterHeader matterId={matterId} />}
        <main className="min-w-0">{children}</main>
      </div>
    </div>
  );
}
