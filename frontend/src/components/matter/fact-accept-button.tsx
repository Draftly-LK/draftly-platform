"use client";

import { useEffect, useRef, useState } from "react";
import { useTranslations } from "next-intl";
import { AlertTriangle, Check, LoaderCircle } from "lucide-react";
import { Button } from "@/components/ui/button";
import { ApiError, type TokenProvider } from "@/lib/api/client";
import { getMe } from "@/lib/api/auth";
import { reviewMatterFact } from "@/lib/api/facts";
import {
  clearManualIntent,
  pendingOperationIntent,
  type ManualIntent,
} from "@/lib/api/mutation-intent";
import type { ApiMatterFact } from "@/types/rta";
import { RegisterError } from "./fact-register-common";

/** Accept the displayed observation; changes and conflict decisions use full review. */
export function FactAcceptButton({
  matterId,
  fact,
  getToken,
  onSaved,
  onReview,
  reviewing,
  reviewError,
}: {
  matterId: string;
  fact: ApiMatterFact;
  getToken: TokenProvider;
  onSaved: (fact: ApiMatterFact) => void;
  onReview: () => void;
  reviewing: boolean;
  reviewError?: unknown;
}) {
  const t = useTranslations("factRegister");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const [retryUnavailable, setRetryUnavailable] = useState(false);
  const pending = useRef(false);
  const mounted = useRef(true);
  useEffect(() => {
    mounted.current = true;
    return () => {
      mounted.current = false;
    };
  }, []);

  async function accept() {
    if (pending.current) return;
    if (
      fact.evidenceStale ||
      !fact.evidence.length ||
      !fact.scopeToken ||
      fact.conflictFactIds.length
    ) {
      onReview();
      return;
    }
    pending.current = true;
    setBusy(true);
    setError(null);
    let intent: ManualIntent | undefined;
    try {
      const token = await getToken();
      const actorToken = async () => token;
      const actor = await getMe(actorToken);
      const body = { expectedScopeToken: fact.scopeToken, resolveFactIds: [] };
      intent = await pendingOperationIntent(
        actor.id,
        matterId,
        `fact:${fact.id}:accept`,
        body,
        fact.version,
      );
      setRetryUnavailable(!intent.persistent);
      if (!mounted.current) return;
      const saved = await reviewMatterFact(
        actorToken,
        matterId,
        fact.id,
        "accept",
        body,
        intent.expectedVersion ?? fact.version,
        intent.key,
      );
      if (saved.matterId !== matterId) throw new Error("Foreign fact response");
      clearManualIntent(intent);
      if (mounted.current) onSaved(saved);
    } catch (cause) {
      if (!mounted.current) return;
      setError(cause);
      if (cause instanceof ApiError && [409, 412].includes(cause.status)) {
        if (intent && !intent.reused) clearManualIntent(intent);
        onReview();
      }
    } finally {
      pending.current = false;
      if (mounted.current) setBusy(false);
    }
  }

  return (
    <div className="space-y-2">
      <Button
        variant="primary"
        disabled={busy || reviewing}
        aria-busy={busy}
        onClick={() => void accept()}
      >
        {busy ? (
          <LoaderCircle
            aria-hidden="true"
            className="size-4 animate-spin motion-reduce:animate-none"
          />
        ) : (
          <Check aria-hidden="true" className="size-4" />
        )}
        {t("quickAccept")}
      </Button>
      {error !== null &&
        !(
          reviewing &&
          error instanceof ApiError &&
          [401, 403].includes(error.status) &&
          reviewError instanceof ApiError &&
          reviewError.status === error.status &&
          reviewError.code === error.code
        ) &&
        (error instanceof ApiError && error.status === 412 ? (
          <div
            role="alert"
            className="border-amber bg-amber-bg text-amber-text flex gap-2 rounded border p-3 text-sm"
          >
            <AlertTriangle aria-hidden="true" className="size-4 shrink-0" />
            <p>{t("staleReview")}</p>
          </div>
        ) : (
          <RegisterError cause={error} />
        ))}
      {retryUnavailable && (
        <p role="status" className="text-amber-text text-sm">
          {t("retryStorageUnavailable")}
        </p>
      )}
    </div>
  );
}
