"use client";

/**
 * UserButton — shows the signed-in user's profile image from Clerk.
 *
 * Behaviour:
 * - When Clerk is configured (NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY is set):
 *   renders <UserButton> from @clerk/nextjs, which shows the user's real
 *   profile photo and opens Clerk's user management modal on click.
 * - When Clerk is not configured (demo / CI mode):
 *   renders a styled avatar with the user's initials from the demo store.
 *
 * Either way the component shows in the sidebar footer alongside the
 * existing Settings and Help links.
 */

import { useEffect, useState } from "react";
import { useDemoStore } from "@/lib/store";

/* ── Clerk import guard ──────────────────────────────────────────────────────
 * We import lazily so the build succeeds even without Clerk env vars.
 * If the publishable key is missing, Clerk's ClerkProvider will simply skip
 * initialisation; we fall back to the initials avatar below.
 */
const CLERK_PK = process.env.NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY ?? "";

function getInitials(name: string): string {
  return name
    .split(" ")
    .filter(Boolean)
    .slice(0, 2)
    .map((w) => w[0]?.toUpperCase() ?? "")
    .join("");
}

/** Role → tailwind badge colour */
const ROLE_COLOURS: Record<string, string> = {
  approver: "bg-forest/15 text-forest",
  administrator: "bg-amber-100 text-amber-800",
  maintainer: "bg-violet-100 text-violet-800",
  reviewer: "bg-sky-100 text-sky-800",
};

export function UserButton() {
  const user = useDemoStore((s) => s.matters); // we only need the store to stay reactive
  const demoUser = useDemoStore(() => ({
    name: "N. M. Silva",
    role: "approver" as const,
  }));

  const [ClerkUserButton, setClerkUserButton] = useState<React.ComponentType<{
    appearance?: object;
    afterSignOutUrl?: string;
  }> | null>(null);

  useEffect(() => {
    if (!CLERK_PK) return;
    // Lazy-load so Clerk SDK is only active when the key is present
    import("@clerk/nextjs")
      .then((mod) => {
        setClerkUserButton(() => mod.UserButton as typeof ClerkUserButton);
      })
      .catch(() => {
        // Clerk unavailable — stay on initials fallback
      });
  }, []);

  // ── Demo / initials fallback ──────────────────────────────────────────────
  if (!CLERK_PK || !ClerkUserButton) {
    const initials = getInitials(demoUser.name);
    const roleClass =
      ROLE_COLOURS[demoUser.role] ?? "bg-slate-100 text-slate-600";
    return (
      <div className="flex items-center gap-3 px-3 py-2">
        {/* Avatar circle with initials */}
        <div
          aria-hidden="true"
          className="bg-forest text-white grid size-9 shrink-0 place-items-center rounded-full text-sm font-semibold"
        >
          {initials}
        </div>
        <div className="min-w-0 flex-1">
          <div className="truncate text-sm font-medium leading-tight">
            {demoUser.name}
          </div>
          <div
            className={`mt-0.5 inline-flex items-center rounded px-1.5 py-0.5 text-xs font-medium capitalize ${roleClass}`}
          >
            {demoUser.role}
          </div>
        </div>
      </div>
    );
  }

  // ── Live Clerk user button ────────────────────────────────────────────────
  return (
    <div className="flex items-center gap-3 px-3 py-2">
      <ClerkUserButton
        afterSignOutUrl="/"
        appearance={{
          elements: {
            avatarBox: "size-9 rounded-full ring-2 ring-forest/30",
          },
        }}
      />
      <span className="text-muted-ink truncate text-sm">My profile</span>
    </div>
  );
}
