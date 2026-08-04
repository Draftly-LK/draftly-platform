"use client";

/**
 * UserButton — shows the signed-in user's profile image from Clerk.
 *
 * Behaviour:
 * - When Clerk is configured (NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY is set):
 *   renders <UserButton> from @clerk/nextjs, which shows the user's real
 *   profile photo and opens Clerk's user management modal on click.
 * - When Clerk is not configured (demo / CI mode):
 *   renders a styled avatar with the user's initials and role badge.
 */

import { useEffect, useState } from "react";

/* ── Clerk env guard ────────────────────────────────────────────────────────
 * Public key is safe to read at module scope — it is a build-time env var.
 */
const CLERK_PK = process.env.NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY ?? "";

/** Produce 1-2 uppercase initials from a display name. */
function getInitials(name: string): string {
  return name
    .split(" ")
    .filter(Boolean)
    .slice(0, 2)
    .map((w) => w[0]?.toUpperCase() ?? "")
    .join("");
}

/** Role → Tailwind badge colour classes. */
const ROLE_COLOURS: Record<string, string> = {
  approver: "bg-green-100 text-green-800",
  administrator: "bg-amber-100 text-amber-800",
  maintainer: "bg-violet-100 text-violet-800",
  reviewer: "bg-sky-100 text-sky-800",
};

/** Static demo-mode identity — no store subscription needed. */
const DEMO_USER = { name: "N. M. Silva", role: "approver" } as const;

export function UserButton() {
  const [ClerkUserButton, setClerkUserButton] = useState<React.ComponentType<{
    appearance?: object;
    afterSignOutUrl?: string;
  }> | null>(null);

  useEffect(() => {
    if (!CLERK_PK) return;
    // Lazy-load so the Clerk SDK is only active when the publishable key exists.
    import("@clerk/nextjs")
      .then((mod) => {
        setClerkUserButton(() => mod.UserButton as typeof ClerkUserButton);
      })
      .catch(() => {
        // Clerk unavailable — remain on the initials fallback.
      });
  }, []); // ← empty deps: run once on mount only

  // ── Live Clerk user button ────────────────────────────────────────────────
  if (CLERK_PK && ClerkUserButton) {
    return (
      <div className="flex items-center gap-3 px-3 py-2">
        <ClerkUserButton
          afterSignOutUrl="/"
          appearance={{
            elements: {
              avatarBox: "size-9 rounded-full ring-2 ring-green-700/30",
            },
          }}
        />
        <span className="text-muted-ink truncate text-sm">My profile</span>
      </div>
    );
  }

  // ── Demo / initials fallback ──────────────────────────────────────────────
  const initials = getInitials(DEMO_USER.name);
  const roleClass = ROLE_COLOURS[DEMO_USER.role] ?? "bg-slate-100 text-slate-600";

  return (
    <div className="flex items-center gap-3 px-3 py-2">
      {/* Avatar circle with initials */}
      <div
        aria-hidden="true"
        className="grid size-9 shrink-0 place-items-center rounded-full bg-green-800 text-sm font-semibold text-white"
      >
        {initials}
      </div>
      <div className="min-w-0 flex-1">
        <div className="truncate text-sm font-medium leading-tight">
          {DEMO_USER.name}
        </div>
        <span
          className={`mt-0.5 inline-flex items-center rounded px-1.5 py-0.5 text-xs font-medium capitalize ${roleClass}`}
        >
          {DEMO_USER.role}
        </span>
      </div>
    </div>
  );
}
