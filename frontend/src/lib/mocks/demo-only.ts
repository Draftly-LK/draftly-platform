import { isApiEnabled } from "@/lib/api/client";

/**
 * Fixture case data (matters, documents, facts, obligations, ...) exists for
 * the no-backend demo and for tests. Once the API is configured the app shows
 * what the database returns, or nothing: this yields an empty list then, so no
 * fixture can leak into a live deployment.
 *
 * Catalogue content that is product data rather than case data (form templates,
 * question sets, workflow definitions) is not wrapped in this.
 */
export function demoOnly<T>(fixture: readonly T[]): T[] {
  return isApiEnabled() ? [] : [...fixture];
}
