"use client";

import { useEffect, useState, type RefObject } from "react";

/**
 * Whether a floating control currently sits over a navy surface
 * (`data-surface="inverse"`), rechecked on scroll, resize and layout change,
 * so the control can switch between ink and white to stay legible.
 */
export function useOverInverseSurface(
  ref: RefObject<HTMLElement | null>,
  initial: boolean,
  resetKey: string,
): boolean {
  const [overInverse, setOverInverse] = useState(initial);

  useEffect(() => {
    let frame = 0;
    const check = () => {
      frame = 0;
      const control = ref.current;
      if (!control) return;
      const box = control.getBoundingClientRect();
      if (box.width === 0) return; // hidden (wide screens): nothing to match
      const behind = document
        .elementsFromPoint(box.left + box.width / 2, box.top + box.height / 2)
        .find((node) => !control.contains(node));
      setOverInverse(Boolean(behind?.closest('[data-surface="inverse"]')));
    };
    const schedule = () => {
      if (!frame) frame = requestAnimationFrame(check);
    };
    check();
    // Capture catches scrolling inside any container, not only the window.
    window.addEventListener("scroll", schedule, { passive: true, capture: true });
    window.addEventListener("resize", schedule);
    const layout = new ResizeObserver(schedule);
    layout.observe(document.body);
    return () => {
      cancelAnimationFrame(frame);
      window.removeEventListener("scroll", schedule, { capture: true });
      window.removeEventListener("resize", schedule);
      layout.disconnect();
    };
  }, [ref, resetKey]);

  return overInverse;
}
