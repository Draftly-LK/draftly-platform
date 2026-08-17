"use client";

import { useAuth } from "@clerk/nextjs";
import { useCallback } from "react";
import type { TokenProvider } from "@/lib/api/client";

/**
 * Binds Clerk's session token to the API client for client components.
 *
 * Clerk refreshes short-lived session JWTs, so the token is fetched per call
 * rather than captured once — a cached token would start failing `verify_exp`
 * in clerk_adapter.py partway through a session.
 */
export function useTokenProvider(): TokenProvider {
  const { getToken } = useAuth();
  return useCallback(() => getToken(), [getToken]);
}
