import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { api } from "./api";

describe("api client", () => {
  const fetchMock = vi.fn();
  beforeEach(() => {
    fetchMock.mockReset();
    globalThis.fetch = fetchMock as unknown as typeof fetch;
  });
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("createDraft POSTs to /v1/drafts", async () => {
    fetchMock.mockResolvedValueOnce({
      ok: true,
      json: async () => ({ id: "d1", name: "Test", status: "pending" }),
    });
    await api.createDraft({ num_rounds: 4 });
    expect(fetchMock).toHaveBeenCalledWith(
      "/v1/drafts",
      expect.objectContaining({ method: "POST" }),
    );
  });

  it("listDrafts GETs /v1/drafts", async () => {
    fetchMock.mockResolvedValueOnce({ ok: true, json: async () => [] });
    await api.listDrafts();
    expect(fetchMock).toHaveBeenCalledWith("/v1/drafts", expect.any(Object));
  });

  it("listPlayers builds query string from filters", async () => {
    fetchMock.mockResolvedValueOnce({ ok: true, json: async () => [] });
    await api.listPlayers({ position: "C", q: "Realmuto" });
    const [url] = fetchMock.mock.calls[0];
    expect(url).toBe("/v1/players?position=C&q=Realmuto");
  });

  it("adpTrends includes view param", async () => {
    fetchMock.mockResolvedValueOnce({ ok: true, json: async () => [] });
    await api.adpTrends("overdrafted");
    expect(fetchMock).toHaveBeenCalledWith(
      "/v1/adp/trends?view=overdrafted",
      expect.any(Object),
    );
  });

  it("throws on non-ok status with body text", async () => {
    fetchMock.mockResolvedValueOnce({
      ok: false,
      status: 404,
      statusText: "Not Found",
      text: async () => "draft missing",
    });
    await expect(api.getDraft("nope")).rejects.toThrow(/404/);
  });

  it("streamUrl returns the SSE path", () => {
    expect(api.streamUrl("abc")).toBe("/v1/drafts/abc/stream");
  });
});
