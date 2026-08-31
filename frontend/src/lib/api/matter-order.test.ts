import { describe, expect, it } from "vitest";
import { orderMattersByRecentActivity } from "./matter-order";
import type { ApiRtaMatter } from "@/types/rta";

function matter(id: string, updatedAt: string): ApiRtaMatter {
  return { id, updatedAt } as ApiRtaMatter;
}

describe("orderMattersByRecentActivity", () => {
  it("orders a copy by newest activity and leaves the response untouched", () => {
    const response = [
      matter("mat_old", "2026-08-28T10:00:00Z"),
      matter("mat_new", "2026-08-30T10:00:00Z"),
      matter("mat_middle", "2026-08-29T10:00:00Z"),
    ];

    expect(
      orderMattersByRecentActivity(response).map((item) => item.id),
    ).toEqual(["mat_new", "mat_middle", "mat_old"]);
    expect(response.map((item) => item.id)).toEqual([
      "mat_old",
      "mat_new",
      "mat_middle",
    ]);
  });
});
