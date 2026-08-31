"use client";

import { useEffect, useState } from "react";
import { orderMattersByRecentActivity } from "@/lib/api/matter-order";
import { listMatters } from "@/lib/api/matters";
import { useTokenProvider } from "@/lib/api/use-token-provider";
import type { ApiRtaMatter } from "@/types/rta";

interface RecentMattersState {
  matters: ApiRtaMatter[];
  loading: boolean;
  failed: boolean;
}

/** Fetch the authenticated user's matter feed for client-side workspace UI. */
export function useRecentMatters(fetchLimit = 50): RecentMattersState {
  const getToken = useTokenProvider();
  const [state, setState] = useState<RecentMattersState>({
    matters: [],
    loading: true,
    failed: false,
  });

  useEffect(() => {
    let active = true;
    setState({ matters: [], loading: true, failed: false });

    void listMatters(getToken, { limit: fetchLimit })
      .then((response) => {
        if (!active) return;
        setState({
          matters: orderMattersByRecentActivity(response.items),
          loading: false,
          failed: false,
        });
      })
      .catch(() => {
        if (!active) return;
        setState({ matters: [], loading: false, failed: true });
      });

    return () => {
      active = false;
    };
  }, [fetchLimit, getToken]);

  return state;
}
