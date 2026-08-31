import type { ApiRtaMatter } from "@/types/rta";

/**
 * Return a newest-activity-first copy without mutating the API response.
 *
 * The matters endpoint currently pages by creation time. Recent-work surfaces
 * mean last activity, so they order the fetched page by `updatedAt` before
 * applying their smaller display limit.
 */
export function orderMattersByRecentActivity(
  matters: readonly ApiRtaMatter[],
): ApiRtaMatter[] {
  return [...matters].sort(
    (left, right) =>
      Date.parse(right.updatedAt) - Date.parse(left.updatedAt) ||
      right.id.localeCompare(left.id),
  );
}
