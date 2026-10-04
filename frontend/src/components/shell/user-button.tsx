"use client";

import { createContext, use } from "react";

export function getInitials(name: string): string {
  return name
    .split(" ")
    .filter(Boolean)
    .slice(0, 2)
    .map((word) => word[0]?.toUpperCase() ?? "")
    .join("");
}

export function clerkDisplayName(user: {
  fullName: string | null;
  firstName: string | null;
  lastName: string | null;
  username: string | null;
}): string {
  const full = user.fullName?.trim();
  if (full) return full;
  const parts = [user.firstName, user.lastName]
    .filter(Boolean)
    .join(" ")
    .trim();
  if (parts) return parts;
  return user.username?.trim() ?? "";
}

/**
 * Demo mode depends on server-only env vars, so the root layout resolves it and
 * the account menu (and anything else that must not call Clerk hooks) reads it
 * from here.
 */
// Defaults to demo: with no provider above (tests, isolated renders) there is
// no ClerkProvider either, and the Clerk hooks would throw.
const DemoModeContext = createContext(true);

export function UserButtonProvider({
  demoMode,
  children,
}: {
  demoMode: boolean;
  children: React.ReactNode;
}) {
  return <DemoModeContext value={demoMode}>{children}</DemoModeContext>;
}

export function useDemoMode(): boolean {
  return use(DemoModeContext);
}
