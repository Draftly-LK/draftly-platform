import { describe, expect, it } from "vitest";
import { itSendsEach, token, recordFetches } from "@/test/fetch-recorder";
import {
  approveReviewCandidate,
  editReviewCandidate,
  getDocumentInbox,
  getDocumentReview,
  getPrivateDocumentArtifact,
  getSourceFile,
  listSourceFiles,
  processSourceFile,
  recordBoundaryDecision,
  recordClassificationDecision,
  supersedeSourceFile,
  uploadSourceFile,
} from "./documents";

const recorder = recordFetches();
const FRAGMENTS = {
  fragments: [{ sourceFileId: "src-1", pageStart: 1, pageEnd: 2 }],
};
const SUPERSEDE = {
  supersededBySourceFileId: "src-2",
  reason: "Synthetic rescan",
};

describe("document accessors", () => {
  itSendsEach(recorder, [
    {
      name: "getDocumentReview",
      call: () => getDocumentReview(token, "doc-1"),
      method: "GET",
      path: "/api/v1/detected-documents/doc-1/review",
    },
    {
      name: "editReviewCandidate",
      call: () => editReviewCandidate(token, "cand-1", "Synthetic value", 2),
      method: "PATCH",
      path: "/api/v1/candidate-fields/cand-1",
      body: { value: "Synthetic value" },
      ifMatch: 2,
    },
    {
      name: "approveReviewCandidate",
      call: () => approveReviewCandidate(token, "cand-1", 3),
      method: "POST",
      path: "/api/v1/candidate-fields/cand-1/approve",
      ifMatch: 3,
    },
    {
      name: "listSourceFiles",
      call: () => listSourceFiles(token, "mat-1"),
      method: "GET",
      path: "/api/v1/matters/mat-1/source-files",
    },
    {
      name: "getSourceFile",
      call: () => getSourceFile(token, "src-1"),
      method: "GET",
      path: "/api/v1/source-files/src-1",
    },
    {
      name: "processSourceFile",
      call: () => processSourceFile(token, "src-1", 4),
      method: "POST",
      path: "/api/v1/source-files/src-1/process",
      ifMatch: 4,
    },
    {
      name: "supersedeSourceFile",
      call: () => supersedeSourceFile(token, "src-1", SUPERSEDE, 5),
      method: "POST",
      path: "/api/v1/source-files/src-1/supersede",
      body: SUPERSEDE,
      ifMatch: 5,
    },
    {
      name: "getDocumentInbox",
      call: () => getDocumentInbox(token, "mat-1"),
      method: "GET",
      path: "/api/v1/matters/mat-1/document-inbox",
    },
    {
      name: "recordBoundaryDecision",
      call: () => recordBoundaryDecision(token, "doc-1", FRAGMENTS, 6),
      method: "POST",
      path: "/api/v1/detected-documents/doc-1/boundary-decisions",
      body: FRAGMENTS,
      ifMatch: 6,
    },
    {
      name: "recordClassificationDecision",
      call: () =>
        recordClassificationDecision(token, "doc-1", { classId: "cls-1" }, 7),
      method: "POST",
      path: "/api/v1/detected-documents/doc-1/classification-decisions",
      body: { classId: "cls-1" },
      ifMatch: 7,
    },
  ]);
});

describe("uploadSourceFile", () => {
  const file = new File(["%PDF-1.4 synthetic"], "synthetic.pdf", {
    type: "application/pdf",
  });

  it("sends the file as multipart form data under `file`", async () => {
    await uploadSourceFile(token, "mat-1", file);

    const request = recorder.only();
    expect(request).toMatchObject({
      method: "POST",
      path: "/api/v1/matters/mat-1/source-files",
    });
    expect(request.body).toBeInstanceOf(FormData);
    expect((request.body as FormData).get("file")).toBeInstanceOf(File);
    expect(((request.body as FormData).get("file") as File).name).toBe(
      "synthetic.pdf",
    );
  });

  it("leaves Content-Type to the browser, so the multipart boundary is set", async () => {
    await uploadSourceFile(token, "mat-1", file);

    expect(recorder.only().headers["Content-Type"]).toBeUndefined();
  });
});

describe("list queries", () => {
  it("listSourceFiles sends limit and cursor", async () => {
    await listSourceFiles(token, "mat-1", { limit: 10, cursor: "abc" });

    expect(recorder.only().path).toBe(
      "/api/v1/matters/mat-1/source-files?limit=10&cursor=abc",
    );
  });

  it("getDocumentInbox sends limit and cursor", async () => {
    await getDocumentInbox(token, "mat-1", { limit: 5, cursor: "xyz" });

    expect(recorder.only().path).toBe(
      "/api/v1/matters/mat-1/document-inbox?limit=5&cursor=xyz",
    );
  });
});

describe("private document artifacts", () => {
  it("fetches the derivative as an authenticated blob", async () => {
    const blob = await getPrivateDocumentArtifact(token, "/api/v1/artifacts/art-1");
    expect(blob).toBeInstanceOf(Blob);
    const request = recorder.only();
    expect(request.method).toBe("GET");
    expect(request.path).toBe("/api/v1/artifacts/art-1");
    expect(request.headers.Authorization).toBe("Bearer synthetic-token");
  });
});
