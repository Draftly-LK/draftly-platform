import { Sidebar } from "./sidebar";
import { MatterHeader } from "./matter-header";

export function AppShell({ children, matterId }: { children: React.ReactNode; matterId?: string }) {
  return <div className="min-h-screen bg-canvas"><Sidebar /><div className="min-w-0 md:pl-[244px]">{matterId && <MatterHeader matterId={matterId} />}<main className="min-w-0">{children}</main></div></div>;
}

