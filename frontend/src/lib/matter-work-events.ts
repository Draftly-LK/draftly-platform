/** Same-tab refresh only; authoritative decisions stay in their owning services. */
export const MATTER_WORK_CHANGED = "draftly:matter-work-changed";

export function notifyMatterWorkChanged(matterId: string): void {
  window.dispatchEvent(
    new CustomEvent(MATTER_WORK_CHANGED, { detail: { matterId } }),
  );
}
