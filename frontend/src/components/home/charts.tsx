/**
 * Small, dependency-free SVG charts for the home page. Colour is never the only
 * cue: every chart sits beside a legend or a sentence that carries the numbers,
 * and each mark has a native tooltip.
 */

/** Validated against the white card: lightness band, chroma, colour-blind and normal-vision separation, 3:1. */
export const STAGE_COLORS = { progress: "#5a62c4", review: "#c0882b", drafting: "#00918a" } as const;

const SIZE = 120;
const CENTER = SIZE / 2;
const RADIUS = 46;
const STROKE = 13;
const CIRCUMFERENCE = 2 * Math.PI * RADIUS;
/** Arc left empty between segments. Round caps eat STROKE of it, leaving a ~3px visible gap. */
const GAP = STROKE + 3;

export interface DonutSegment {
  key: string;
  value: number;
  color: string;
  label: string;
}

/** A ring split into rounded segments with a small gap between them; empty shows the bare track. */
export function DonutChart({ segments, label, children }: { segments: DonutSegment[]; label: string; children?: React.ReactNode }) {
  const shown = segments.filter((segment) => segment.value > 0);
  const total = shown.reduce((sum, segment) => sum + segment.value, 0);
  const single = shown.length === 1;
  let start = 0;
  return (
    <div className="home-insight-ring relative shrink-0">
      <svg viewBox={`0 0 ${SIZE} ${SIZE}`} role="img" aria-label={label} className="home-chart-in size-full -rotate-90">
        <circle cx={CENTER} cy={CENTER} r={RADIUS} fill="none" stroke="var(--border)" strokeWidth={STROKE} />
        {total > 0 &&
          shown.map((segment) => {
            const share = (segment.value / total) * CIRCUMFERENCE;
            // A one-stage pipeline is a whole ring: no caps, no gap.
            const length = single ? CIRCUMFERENCE : Math.max(share - GAP, 0.01);
            const offset = start + (single ? 0 : GAP / 2);
            start += share;
            return (
              <circle
                key={segment.key}
                cx={CENTER}
                cy={CENTER}
                r={RADIUS}
                fill="none"
                stroke={segment.color}
                strokeWidth={STROKE}
                strokeLinecap={single ? "butt" : "round"}
                strokeDasharray={`${length} ${CIRCUMFERENCE}`}
                strokeDashoffset={-offset}
              >
                <title>{`${segment.label}: ${segment.value}`}</title>
              </circle>
            );
          })}
      </svg>
      {children ? <div className="absolute inset-0 flex flex-col items-center justify-center text-center">{children}</div> : null}
    </div>
  );
}

/** A compact progress ring for a list row: the percentage sits beside it, so it is never the only cue. */
export function MiniRing({ percent, label }: { percent: number; label: string }) {
  const length = (Math.min(100, Math.max(0, percent)) / 100) * CIRCUMFERENCE;
  return (
    <svg viewBox={`0 0 ${SIZE} ${SIZE}`} role="img" aria-label={label} className="size-5 shrink-0 -rotate-90">
      <circle cx={CENTER} cy={CENTER} r={RADIUS} fill="none" stroke="var(--border)" strokeWidth={22} />
      {length > 0 ? (
        <circle cx={CENTER} cy={CENTER} r={RADIUS} fill="none" stroke="var(--forest)" strokeWidth={22} strokeDasharray={`${length} ${CIRCUMFERENCE}`} />
      ) : null}
    </svg>
  );
}

const BAR_WIDTH = 8;
const BAR_GAP = 5;
const BAR_HEIGHT = 44;

/** One bar per day; a day with nothing due is a small dot on the baseline. */
export function DayBars({ counts, titles, label, highlight }: {
  counts: readonly number[];
  titles: readonly string[];
  label: string;
  /** Days that are urgent (for example, due within two days) are drawn in amber. */
  highlight?: (index: number) => boolean;
}) {
  const max = Math.max(1, ...counts);
  const width = counts.length * (BAR_WIDTH + BAR_GAP) - BAR_GAP;
  return (
    <svg viewBox={`0 0 ${width} ${BAR_HEIGHT}`} role="img" aria-label={label} preserveAspectRatio="none" className="home-chart-in h-11 w-full">
      {counts.map((count, index) => {
        const x = index * (BAR_WIDTH + BAR_GAP);
        if (count === 0) {
          return (
            <rect key={index} x={x + BAR_WIDTH / 2 - 1.5} y={BAR_HEIGHT - 3} width={3} height={3} rx={1.5} fill="var(--border-strong)">
              <title>{titles[index]}</title>
            </rect>
          );
        }
        const height = Math.max(8, (count / max) * BAR_HEIGHT);
        return (
          <rect
            key={index}
            x={x}
            y={BAR_HEIGHT - height}
            width={BAR_WIDTH}
            height={height}
            rx={3}
            fill={highlight?.(index) ? STAGE_COLORS.review : "var(--forest)"}
          >
            <title>{titles[index]}</title>
          </rect>
        );
      })}
    </svg>
  );
}
