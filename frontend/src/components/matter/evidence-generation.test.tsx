// @vitest-environment happy-dom
import { NextIntlClientProvider } from "next-intl";
import { fireEvent, screen } from "@testing-library/react";
import { expect, it, vi } from "vitest";
import { renderWithIntl } from "@/test/render";
import en from "@/lib/i18n/messages/en.json";
import type {
  ApiDetectedDocument,
  ApiFactEvidenceInput,
  ApiSourceFile,
} from "@/types/rta";
import { EvidenceSelector } from "./fact-evidence";
const sources = ["synthetic-a", "synthetic-b"].map((id) => ({
  id,
  sha256: id,
  originalFilename: id,
  pageCount: 2,
  state: "PROCESSED",
})) as ApiSourceFile[];
const document = {
  id: "synthetic-doc",
  interpretationGeneration: 2,
  extractionState: "unsupported",
  fragments: [
    {
      sourceFileId: "synthetic-b",
      pageStart: 1,
      pageEnd: 1,
      orderInDocument: 0,
    },
  ],
} as ApiDetectedDocument;
it("pins manual source and page to the viewed document only when that exact pair belongs to it", () => {
  const changed = vi.fn();
  const view = renderWithIntl(
    <EvidenceSelector
      sources={sources}
      value={undefined}
      onChange={changed}
      documentContext={document}
    />,
  );
  fireEvent.change(screen.getByLabelText(en.factRegister.evidenceSource), {
    target: { value: "synthetic-a" },
  });
  expect(changed.mock.calls.at(-1)?.[0].detectedDocumentId).toBeUndefined();
  fireEvent.change(screen.getByLabelText(en.factRegister.evidenceSource), {
    target: { value: "synthetic-b" },
  });
  const pinned = changed.mock.calls.at(-1)?.[0] as ApiFactEvidenceInput;
  expect(pinned).toMatchObject({
    sourceFileId: "synthetic-b",
    pageNumber: 1,
    detectedDocumentId: "synthetic-doc",
    interpretationGeneration: 2,
  });
  view.rerender(
    <NextIntlClientProvider locale="en" messages={en}>
      <EvidenceSelector
        sources={sources}
        value={pinned}
        onChange={changed}
        documentContext={{ ...document, interpretationGeneration: 3 }}
      />
    </NextIntlClientProvider>,
  );
  changed.mockClear();
  fireEvent.change(
    screen.getByRole("textbox", { name: /Supporting excerpt/ }),
    {
      target: { value: "SYNTHETIC excerpt" },
    },
  );
  expect(changed.mock.calls.at(-1)?.[0].interpretationGeneration).toBe(2);
  fireEvent.click(
    screen.getByRole("button", { name: "Use this current document page" }),
  );
  expect(changed.mock.calls.at(-1)?.[0].interpretationGeneration).toBe(3);
});
it.each(["retired", "page-left"])(
  "does not renew evidence when %s",
  (state) => {
    const value = {
      sourceFileId: "synthetic-b",
      sourceSha256: "synthetic-b",
      pageNumber: 1,
      detectedDocumentId: document.id,
      interpretationGeneration: 1,
    };
    renderWithIntl(
      <EvidenceSelector
        sources={sources}
        value={value}
        onChange={vi.fn()}
        documentContext={{
          ...document,
          ...(state === "retired"
            ? { versionRelationship: "SUPERSEDED" as const }
            : { fragments: [] }),
        }}
      />,
    );
    expect(
      screen.getByText(
        "The selected document page changed. Review its current grouping before using it.",
      ),
    ).toBeTruthy();
    expect(
      screen.queryByRole("button", { name: "Use this current document page" }),
    ).toBeNull();
  },
);
