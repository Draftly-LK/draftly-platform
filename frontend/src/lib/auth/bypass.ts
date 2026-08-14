/**
 * Dev-only auth bypass. Delete this module and AUTH_BYPASS when retiring the
 * shortcut — call sites: middleware + AppShell (demo chrome).
 *
 * AUTH_BYPASS is not NEXT_PUBLIC_, so the browser never receives the value.
 * Production always returns false even if the env var is set by mistake.
 */
export function isAuthBypassEnabled(): boolean {
  if (process.env.NODE_ENV === "production") {
    return false;
  }
  return process.env.AUTH_BYPASS === "true";
}

/** Log if someone sets AUTH_BYPASS in production; the flag is still ignored. */
export function warnIfBypassSetInProduction(): void {
  if (process.env.NODE_ENV === "production" && process.env.AUTH_BYPASS === "true") {
    console.error(
      "[draftly] AUTH_BYPASS=true is set but NODE_ENV=production — bypass ignored. Unset AUTH_BYPASS in deploy env.",
    );
  }
}
