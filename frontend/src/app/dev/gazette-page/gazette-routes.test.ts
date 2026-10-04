import { afterEach, describe, expect, it, vi } from "vitest";
import { GET as legacyPage } from "./[lang]/route";
import { GET as localizedPage } from "./[lang]/[name]/route";

describe("development gazette image routes", () => {
  afterEach(() => vi.unstubAllEnvs());
  const request = new Request(
    "https://synthetic.test/dev/gazette-page/page-04.png",
  );

  it("serves the one-segment image using the shared dynamic segment", async () => {
    vi.stubEnv("NODE_ENV", "development");
    // Both URL shapes share [lang]; on the one-segment URL it is the image name.
    const result = await legacyPage(request, {
      params: Promise.resolve({ lang: "page-04.png" }),
    });
    expect(result.status).toBe(200);
    expect(result.headers.get("content-type")).toBe("image/png");
    expect(
      Array.from(new Uint8Array(await result.arrayBuffer()).slice(0, 8)),
    ).toEqual([137, 80, 78, 71, 13, 10, 26, 10]);
  });

  it("preserves the localized two-segment image URL", async () => {
    vi.stubEnv("NODE_ENV", "development");
    const result = await localizedPage(request, {
      params: Promise.resolve({ lang: "en", name: "page-04.png" }),
    });
    expect(result.status).toBe(200);
    expect(result.headers.get("content-type")).toBe("image/png");
  });

  it("rejects paths outside the fixed image and language allowlists", async () => {
    vi.stubEnv("NODE_ENV", "development");
    expect(
      (
        await legacyPage(request, {
          params: Promise.resolve({ lang: "../private.png" }),
        })
      ).status,
    ).toBe(404);
    expect(
      (
        await localizedPage(request, {
          params: Promise.resolve({ lang: "private", name: "page-04.png" }),
        })
      ).status,
    ).toBe(404);
    expect(
      (
        await localizedPage(request, {
          params: Promise.resolve({ lang: "en", name: "../private.png" }),
        })
      ).status,
    ).toBe(404);
  });

  it("closes both image URLs in production", async () => {
    vi.stubEnv("NODE_ENV", "production");
    expect(
      (
        await legacyPage(request, {
          params: Promise.resolve({ lang: "page-04.png" }),
        })
      ).status,
    ).toBe(404);
    expect(
      (
        await localizedPage(request, {
          params: Promise.resolve({ lang: "en", name: "page-04.png" }),
        })
      ).status,
    ).toBe(404);
  });
});
