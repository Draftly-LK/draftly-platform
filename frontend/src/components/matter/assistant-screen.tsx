"use client";

import { AppShell } from "@/components/shell/app-shell";
import { MatterConversation } from "./matter-conversation";

export function MatterAssistantScreen({ matterId }: { matterId: string }) {
  return (
    <AppShell matterId={matterId}>
      <MatterConversation key={matterId} matterId={matterId} />
    </AppShell>
  );
}
