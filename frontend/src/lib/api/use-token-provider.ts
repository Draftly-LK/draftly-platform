"use client";

import { useAuth } from "@clerk/nextjs";
import { useCallback } from "react";
import type { TokenProvider } from "@/lib/api/client";
import { hasClerkPublishableKey } from "@/lib/auth/clerk";

/**
 * Binds Clerk's session token to the API client for client components.
 *
 * Clerk refreshes short-lived session JWTs, so the token is fetched per call
 * rather than captured once — a cached token would start failing `verify_exp`
 * in clerk_adapter.py partway through a session.
 */
function useClerkTokenProvider(): TokenProvider {
  const { getToken } = useAuth();
  return useCallback(() => getToken(), [getToken]);
}

const noToken: TokenProvider = async () => null;

/** Without Clerk (offline demo, local dev) no `ClerkProvider` is mounted, and
 *  `useAuth` would throw; there is no session, so there is no token. */
function useNoTokenProvider(): TokenProvider {
  return noToken;
}

/**
 * Chosen once per bundle: the publishable key is inlined at build time, so a
 * component always calls the same hook and the rules of hooks hold.
 */
export const useTokenProvider: () => TokenProvider = hasClerkPublishableKey()
  ? useClerkTokenProvider
  : useNoTokenProvider;
