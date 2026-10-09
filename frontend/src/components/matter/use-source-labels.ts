"use client";
import { useEffect, useState } from "react";
import type { TokenProvider } from "@/lib/api/client";
import { getSourceFile } from "@/lib/api/documents";

export function useSourceLabels(
  getToken: TokenProvider,
  ids: (string | null | undefined)[],
  matterId?: string,
) {
  const identity = JSON.stringify(
    [...new Set(ids.filter((id): id is string => Boolean(id)))].sort(),
  );
  const [labels, setLabels] = useState<Record<string, string>>({});
  useEffect(() => {
    let active = true;
    setLabels({});
    void Promise.all(
      (JSON.parse(identity) as string[]).map(async (id) => {
        try {
          const source = await getSourceFile(getToken, id);
          return source.id === id && (!matterId || source.matterId === matterId)
            ? [id, source.originalFilename]
            : null;
        } catch {
          return null;
        }
      }),
    ).then((items) => {
      if (active)
        setLabels(Object.fromEntries(items.filter((item) => item !== null)));
    });
    return () => {
      active = false;
    };
  }, [getToken, identity, matterId]);
  return labels;
}
