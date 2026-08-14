/** True when the public Clerk key is present (safe to read on client or server). */
export function hasClerkPublishableKey(): boolean {
  return Boolean(process.env.NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY);
}

/**
 * True when both Clerk keys needed for middleware/session are set.
 * CLERK_SECRET_KEY is server-only — call only from server / middleware.
 */
export function isClerkConfigured(): boolean {
  return Boolean(
    process.env.NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY && process.env.CLERK_SECRET_KEY,
  );
}
