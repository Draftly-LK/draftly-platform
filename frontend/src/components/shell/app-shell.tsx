import { MatterHeader } from "./matter-header";
import { Sidebar } from "./sidebar";
import { SidebarToggle } from "./sidebar-toggle";

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
      {/* Outside the sidebar's clipping container, so its outer half is never cut off. Rendered first so the
          keyboard reaches it first, matching where it sits (at the top, on the edge). */}
      <SidebarToggle />
      <Sidebar />
      <div className="min-w-0 transition-[padding-left] duration-[180ms] ease-out lg:pl-[var(--sidebar-width)]">
        {matterId && <MatterHeader matterId={matterId} />}
        <main className="min-w-0">{children}</main>
      </div>
    </div>
  );
}
