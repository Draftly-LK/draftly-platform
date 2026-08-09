import { isAuthBypassEnabled } from "@/lib/auth/bypass";
import { isClerkConfigured } from "@/lib/auth/clerk";
import { MatterHeader } from "./matter-header";
import { Sidebar } from "./sidebar";

export function AppShell({
  children,
  matterId,
}: {
  children: React.ReactNode;
  matterId?: string;
}) {
  const demoMode = isAuthBypassEnabled() || !isClerkConfigured();

  return (
    <div className="bg-canvas min-h-screen">
      <Sidebar demoMode={demoMode} />
      <div className="min-w-0 md:pl-[244px]">
        {matterId && <MatterHeader matterId={matterId} />}
        <main className="min-w-0">{children}</main>
      </div>
    </div>
  );
}
