// @vitest-environment happy-dom
import { webcrypto } from "node:crypto";
import { fireEvent, screen, waitFor } from "@testing-library/react";
import { expect, it, vi } from "vitest";
import { renderWithIntl } from "@/test/render";
import en from "@/lib/i18n/messages/en.json";
const mocks = vi.hoisted(() => ({ create: vi.fn(), token: async () => null }));
vi.mock("@/lib/api/client", async (load) => ({
  ...(await load<Record<string, unknown>>()),
  isApiEnabled: () => true,
}));
vi.mock("@/lib/api/auth", () => ({
  getMe: async () => ({ id: "synthetic-lawyer" }),
}));
vi.mock("@/lib/api/use-token-provider", () => ({
  useTokenProvider: () => mocks.token,
}));
vi.mock("@/lib/api/matters", () => ({
  createMatter: mocks.create,
  compileChecklist: vi.fn(),
  confirmSubtype: vi.fn(),
  routeMatter: vi.fn(),
  saveIntakeAnswer: vi.fn(),
}));
vi.mock("next/navigation", () => ({ useRouter: () => ({ push: vi.fn() }) }));
import { NewMatterScreen } from "./new-matter-screen";
it("reuses matter-create intent after remount without storing entered references", async () => {
  sessionStorage.clear();
  vi.stubGlobal("crypto", webcrypto);
  mocks.create
    .mockRejectedValueOnce(new Error("SYNTHETIC network loss"))
    .mockResolvedValue({ id: "synthetic-matter", version: 1 });
  const view = renderWithIntl(<NewMatterScreen />);
  fireEvent.click(screen.getByRole("button", { name: en.newMatter.continue }));
  fireEvent.change(screen.getByLabelText(en.newMatter.matterReference), {
    target: { value: "SYNTHETIC PRIVATE REFERENCE" },
  });
  fireEvent.click(screen.getByRole("button", { name: en.newMatter.next }));
  await waitFor(() => expect(mocks.create).toHaveBeenCalledOnce());
  await screen.findByRole("alert");
  const key = mocks.create.mock.calls[0]![2];
  view.unmount();
  renderWithIntl(<NewMatterScreen />);
  fireEvent.click(screen.getByRole("button", { name: en.newMatter.continue }));
  fireEvent.change(screen.getByLabelText(en.newMatter.matterReference), {
    target: { value: "SYNTHETIC PRIVATE REFERENCE" },
  });
  fireEvent.click(screen.getByRole("button", { name: en.newMatter.next }));
  await waitFor(() => expect(mocks.create).toHaveBeenCalledTimes(2));
  expect(key).toEqual(expect.any(String));
  expect(mocks.create.mock.calls[1]![2]).toBe(key);
  expect(Object.values(sessionStorage).join()).not.toContain(
    "SYNTHETIC PRIVATE REFERENCE",
  );
});
