"use client";

import { createContext, useContext } from "react";

/**
 * Carries MULTILINGUAL_LANGUAGE_SUPPORT to client components. The env var is
 * server-only, so the root layout reads it and passes the resolved boolean
 * down. Defaults to true so any tree rendered without the provider (tests,
 * storybook-style harnesses) keeps the multilingual behaviour.
 */
const MultilingualContext = createContext(true);

export function MultilingualProvider({
  enabled,
  children,
}: {
  enabled: boolean;
  children: React.ReactNode;
}) {
  return <MultilingualContext value={enabled}>{children}</MultilingualContext>;
}

export function useMultilingualEnabled(): boolean {
  return useContext(MultilingualContext);
}
