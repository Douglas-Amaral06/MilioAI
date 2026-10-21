import { afterEach, expect, it, vi } from "vitest";
afterEach(() => {
  vi.unstubAllGlobals();
  vi.unstubAllEnvs();
  vi.resetModules();
});
it.each([true, false])(
  "mantém API real quando offline está desabilitado (DEV=%s)",
  async (dev) => {
    vi.stubEnv("DEV", dev);
    vi.stubGlobal("__LOCAL_DEMO__", false);
    const storage = vi.fn(() => null);
    vi.stubGlobal("sessionStorage", { getItem: storage });
    const fetch = vi
      .fn()
      .mockResolvedValue(
        new Response(JSON.stringify({ id: "real-server" }), { status: 200 }),
      );
    vi.stubGlobal("fetch", fetch);
    const client = await import("./client");
    expect(await client.request("/me")).toEqual({ id: "real-server" });
    expect(fetch).toHaveBeenCalledWith(
      "/api/v1/me",
      expect.objectContaining({
        headers: { "Content-Type": "application/json" },
      }),
    );
    expect(storage).toHaveBeenCalledWith("milioai.auth.session.v1");
  },
);
