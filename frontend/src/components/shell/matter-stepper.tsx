"use client";

import { Check, Pause } from "lucide-react";
import { useTranslations } from "next-intl";
import { cn } from "@/lib/utils";
import type { RtaMatterState } from "@/types/rta";
import { STAGE_ORDER, stageForState } from "./matter-stage";

/** A registered or closed matter has finished every stage. */
const COMPLETE_STATES: ReadonlySet<RtaMatterState> = new Set([
  "REGISTERED",
  "CLOSED",
]);
/** Work has stopped on the current stage; it is not a different stage. */
const HOLD_STATES: ReadonlySet<RtaMatterState> = new Set([
  "LITIGATION_HOLD",
  "CANCELLED",
]);
const DRAFTING_INDEX = STAGE_ORDER.indexOf("drafting");

/**
 * Where the matter is in its six stages: numbered circles joined by a line,
 * finished stages ticked, the current one raised. Every circle carries a label
 * (visible from `sm`, read aloud on phones), and phones also get a one-line
 * "Step 2 of 6" summary, so colour is never the only cue.
 *
 * `hasForm`: a form can be generated while the matter is still in review (the
 * server holds it there until every blocking checklist item is cleared), so a
 * matter with a form shows Drafting as its current stage.
 */
export function MatterStepper({
  state,
  hasForm = false,
}: {
  state: RtaMatterState;
  hasForm?: boolean;
}) {
  const t = useTranslations("matterNav");
  const complete = COMPLETE_STATES.has(state);
  const hold = HOLD_STATES.has(state);
  const stateIndex = STAGE_ORDER.indexOf(stageForState(state));
  const currentIndex = complete
    ? STAGE_ORDER.length
    : hasForm && !hold
      ? Math.max(stateIndex, DRAFTING_INDEX)
      : stateIndex;
  const currentStage =
    STAGE_ORDER[Math.min(currentIndex, STAGE_ORDER.length - 1)];

  return (
    <div className="px-6 pb-4 pt-1">
      <p
        className="text-muted-ink mb-2 text-center text-xs sm:hidden"
        aria-hidden="true"
      >
        {complete
          ? t("progressComplete")
          : t("stepOf", {
              current: currentIndex + 1,
              total: STAGE_ORDER.length,
              stage: t(`stage.${currentStage}`),
            })}
      </p>
      <ol
        aria-label={t("progress")}
        className="mx-auto grid max-w-3xl"
        style={{
          gridTemplateColumns: `repeat(${STAGE_ORDER.length}, minmax(0, 1fr))`,
        }}
      >
        {STAGE_ORDER.map((stage, index) => {
          const done = index < currentIndex;
          const current = index === currentIndex;
          const paused = current && hold;
          const last = index === STAGE_ORDER.length - 1;
          return (
            <li
              key={stage}
              aria-current={current ? "step" : undefined}
              className="relative flex min-w-0 flex-col items-center"
            >
              {!last ? (
                <span
                  aria-hidden="true"
                  className={cn(
                    "absolute left-1/2 top-3.5 h-0.5 w-full -translate-y-1/2 sm:top-4",
                    index < currentIndex ? "bg-forest" : "bg-border",
                  )}
                />
              ) : null}
              <span
                aria-hidden="true"
                className={cn(
                  "relative z-10 grid size-7 place-items-center rounded-full border text-xs font-semibold tabular-nums transition-colors sm:size-8 sm:text-sm",
                  done && "border-forest bg-forest text-white",
                  current &&
                    !paused &&
                    "border-forest bg-forest ring-selected-bg text-white ring-4",
                  paused &&
                    "border-amber bg-amber-bg text-amber-text ring-amber-bg ring-4",
                  !done &&
                    !current &&
                    "border-border-strong bg-surface text-muted-ink",
                )}
              >
                {done ? (
                  <Check className="size-4" strokeWidth={2} />
                ) : paused ? (
                  <Pause className="size-3.5" strokeWidth={2} />
                ) : (
                  index + 1
                )}
              </span>
              {/* The gap sits on a wrapper: `sm:not-sr-only` resets the label's own margin. */}
              <span className="block w-full min-w-0 px-1 sm:mt-2">
                <span
                  className={cn(
                    "sr-only block break-words text-center text-xs [overflow-wrap:anywhere] sm:not-sr-only sm:whitespace-normal",
                    current
                      ? paused
                        ? "text-amber-text font-semibold"
                        : "text-forest font-semibold"
                      : done
                        ? "text-ink"
                        : "text-muted-ink",
                  )}
                >
                  {t(`stage.${stage}`)}
                  <span className="sr-only">
                    {done
                      ? ` (${t("stepDone")})`
                      : paused
                        ? ` (${t("stepOnHold")})`
                        : ""}
                  </span>
                </span>
              </span>
            </li>
          );
        })}
      </ol>
    </div>
  );
}
