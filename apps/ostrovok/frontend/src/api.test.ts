import { afterEach, expect, it, vi } from "vitest";
import { ApiError, request } from "./api";
afterEach(() => vi.unstubAllGlobals());
it("keeps server version conflict errors actionable", async () => {
  vi.stubGlobal(
    "fetch",
    async () =>
      new Response(JSON.stringify({ detail: "Версия поездки изменилась." }), {
        status: 409,
      }),
  );
  await expect(request("/api/trips/example")).rejects.toMatchObject({
    status: 409,
    message: "Версия поездки изменилась.",
  });
});
it("gives a readable error when the API returns an empty gateway failure", async () => {
  vi.stubGlobal("fetch", async () => new Response("", { status: 502 }));
  await expect(request("/api/trips/example")).rejects.toBeInstanceOf(ApiError);
});
it("gives a readable error when the network disconnects", async () => {
  vi.stubGlobal("fetch", async () => {
    throw new TypeError("Failed to fetch");
  });
  await expect(request("/api/trips/example")).rejects.toBeInstanceOf(ApiError);
});
it("preserves request cancellation for the UI recovery flow", async () => {
  vi.stubGlobal("fetch", async () => {
    throw new DOMException("Aborted", "AbortError");
  });
  await expect(request("/api/trips/example")).rejects.toMatchObject({
    name: "AbortError",
  });
});
