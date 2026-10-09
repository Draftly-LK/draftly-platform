// @vitest-environment happy-dom
import { expect, it, vi } from "vitest";
import {
  MATTER_WORK_CHANGED,
  notifyMatterWorkChanged,
} from "./matter-work-events";
it("refreshes only the explicitly named matter without including client records", () => {
  const received = vi.fn();
  window.addEventListener(MATTER_WORK_CHANGED, received);
  notifyMatterWorkChanged("synthetic-matter");
  expect(received).toHaveBeenCalledTimes(1);
  expect((received.mock.calls[0]![0] as CustomEvent).detail).toEqual({
    matterId: "synthetic-matter",
  });
  window.removeEventListener(MATTER_WORK_CHANGED, received);
});
