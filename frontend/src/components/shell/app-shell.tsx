import { MatterHeader } from "./matter-header";
import { Sidebar } from "./sidebar";

export function AppShell({
  children,
  matterId,
}: {
  children: React.ReactNode;
  matterId?: string;
}) {
  // No separate top bar: the profile button sits at the right end of each
  // page or matter header, so the header is the only bar above the content.
  return (
    <div className="bg-canvas min-h-screen">
      <Sidebar />
      <div className="min-w-0 md:pl-[244px]">
        {matterId && <MatterHeader matterId={matterId} />}
        <main className="min-w-0">{children}</main>
      </div>
    </div>
  );
}
