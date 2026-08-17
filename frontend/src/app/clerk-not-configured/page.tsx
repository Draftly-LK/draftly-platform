/**
 * Static error page — shown when NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY or
 * CLERK_SECRET_KEY are missing. The middleware redirects every request here
 * rather than serving the application without authentication (fail-closed).
 *
 * This page intentionally does not use AppShell or any authenticated layout.
 * It is server-only and requires no Clerk context.
 */

export default function ClerkNotConfiguredPage() {
  return (
    <main
      style={{
        display: "flex",
        minHeight: "100vh",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        padding: "2rem",
        fontFamily: "var(--font-plex, system-ui, sans-serif)",
        backgroundColor: "var(--canvas, #f4f3ef)",
        color: "var(--ink, #1b211d)",
        textAlign: "center",
      }}
    >
      <div style={{ maxWidth: "420px" }}>
        <h1
          style={{
            fontSize: "1.5rem",
            fontWeight: 600,
            letterSpacing: "-0.01em",
            marginBottom: "0.5rem",
          }}
        >
          Draftly is not configured
        </h1>
        <p
          style={{
            fontSize: "0.875rem",
            color: "var(--muted-ink, #667068)",
            lineHeight: 1.6,
          }}
        >
          The authentication provider (Clerk) is not set up for this environment.
          Set <code>NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY</code> and{" "}
          <code>CLERK_SECRET_KEY</code> in your environment, then restart the
          server.
        </p>
        <p
          style={{
            marginTop: "1rem",
            fontSize: "0.75rem",
            color: "var(--muted-ink, #667068)",
          }}
        >
          If you are developing locally, set{" "}
          <code>AUTH_BYPASS=true</code> in <code>frontend/.env</code> to skip
          authentication.
        </p>
      </div>
    </main>
  );
}
