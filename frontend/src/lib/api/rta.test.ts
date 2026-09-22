import { describe, expect, it, vi } from "vitest";
import { ApiError } from "./client";
import { itSendsEach, token, recordFetches } from "@/test/fetch-recorder";
import { getRtaDocumentClasses, getRtaQuestions, getRtaTaxonomy } from "./rta";

const recorder = recordFetches({ version: "synthetic" });

describe("RTA contract accessors", () => {
  itSendsEach(recorder, [
    {
      name: "getRtaTaxonomy",
      call: () => getRtaTaxonomy(token),
      method: "GET",
      path: "/api/v1/rta/taxonomy",
    },
    {
      name: "getRtaQuestions",
      call: () => getRtaQuestions(token),
      method: "GET",
      path: "/api/v1/rta/questions",
    },
    {
      name: "getRtaDocumentClasses",
      call: () => getRtaDocumentClasses(token),
      method: "GET",
      path: "/api/v1/rta/document-classes",
    },
  ]);
});

it("returns the parsed contract", async () => {
  await expect(getRtaQuestions(token)).resolves.toEqual({
    version: "synthetic",
  });
});

it("sends nothing when signed out", async () => {
  await expect(getRtaTaxonomy(async () => null)).rejects.toMatchObject({
    code: "unauthenticated",
  });
  expect(recorder.requests).toHaveLength(0);
});

it("turns the error envelope into an ApiError the screen can branch on", async () => {
  vi.stubGlobal(
    "fetch",
    async () =>
      new Response(
        JSON.stringify({
          error: {
            code: "not_found",
            message: "Synthetic",
            correlation_id: "corr-1",
          },
        }),
        { status: 404 },
      ),
  );

  const failure = await getRtaTaxonomy(token).catch((error: unknown) => error);

  expect(failure).toBeInstanceOf(ApiError);
  expect(failure).toMatchObject({
    status: 404,
    code: "not_found",
    correlationId: "corr-1",
  });
});
