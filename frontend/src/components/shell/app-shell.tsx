import { isAuthBypassEnabled } from "@/lib/auth/bypass";
import { isClerkConfigured } from "@/lib/auth/clerk";
import { MatterHeader } from "./matter-header";
import { Sidebar } from "./sidebar";
import { UserButton } from "./user-button";

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
      <Sidebar />
      <div className="min-w-0 md:pl-[244px]">
        <div
          data-app-chrome
          className="border-border bg-surface flex min-h-14 items-center justify-end border-b px-4 sm:px-6"
        >
          <UserButton demoMode={demoMode} />
        </div>
        {matterId && <MatterHeader matterId={matterId} />}
        <main className="min-w-0">{children}</main>
      </div>
    </div>
  );
}
