import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { api } from "./client";

describe("Frontend API Client", () => {
  const originalFetch = global.fetch;

  beforeEach(() => {
    localStorage.clear();
  });

  afterEach(() => {
    global.fetch = originalFetch;
    vi.restoreAllMocks();
  });

  it("attaches default VITE_API_KEY when no API key in localStorage", async () => {
    let capturedHeaders: Headers | undefined;
    global.fetch = vi.fn().mockImplementation((url, options) => {
      capturedHeaders = options?.headers as Headers;
      return Promise.resolve({
        ok: true,
        json: () => Promise.resolve({ status: "healthy" }),
      });
    });

    await api.getHealth();
    expect(capturedHeaders?.get("X-API-Key")).toBe(import.meta.env.VITE_API_KEY || "");
  });

  it("attaches custom API key from localStorage", async () => {
    localStorage.setItem("COLMILLO_API_KEY", "custom-secret-key");
    let capturedHeaders: Headers | undefined;
    global.fetch = vi.fn().mockImplementation((url, options) => {
      capturedHeaders = options?.headers as Headers;
      return Promise.resolve({
        ok: true,
        json: () => Promise.resolve({ status: "healthy" }),
      });
    });

    await api.getHealth();
    expect(capturedHeaders?.get("X-API-Key")).toBe("custom-secret-key");
  });

  it("throws error with detail message on 400 Bad Request", async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 400,
      statusText: "Bad Request",
      json: () => Promise.resolve({ detail: "Unsupported sport: curling" }),
    });

    await expect(
      api.createPick({
        sport: "curling",
        event_date: "2026-09-13",
        home_team: "A",
        away_team: "B",
        top_n: 5,
      })
    ).rejects.toThrow("Unsupported sport: curling");
  });

  it("throws HTTP status when error detail cannot be parsed", async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 502,
      statusText: "Bad Gateway",
      json: () => Promise.reject(new Error("invalid json")),
    });

    await expect(api.getHealth()).rejects.toThrow("HTTP 502: Bad Gateway");
  });

  it("discovers matches via POST /matches/discover", async () => {
    const mockDiscoveryResponse = {
      date_utc: "2026-09-13",
      generated_at_utc: "2026-09-13T12:00:00Z",
      limit_per_sport: 3,
      results: {
        soccer: {
          matches: [
            {
              sport: "soccer",
              home_team: "Arsenal",
              away_team: "Liverpool",
              event_date: "2026-09-13",
              importance: "High",
            },
          ],
        },
      },
    };

    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve(mockDiscoveryResponse),
    });

    const res = await api.discoverMatches({
      date: "2026-09-13",
      sports: ["soccer"],
      limit_per_sport: 3,
    });

    expect(res.results.soccer.matches[0].home_team).toBe("Arsenal");
  });

  it("creates pick and polls status", async () => {
    global.fetch = vi
      .fn()
      .mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve({ id: "pick-123", status: "pending", created_at: "2026-09-13T12:00:00Z" }),
      })
      .mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve({ id: "pick-123", status: "success" }),
      });

    const createRes = await api.createPick({
      sport: "soccer",
      event_date: "2026-09-13",
      home_team: "Arsenal",
      away_team: "Liverpool",
      top_n: 5,
    });
    expect(createRes.id).toBe("pick-123");

    const statusRes = await api.getPickStatus("pick-123");
    expect(statusRes.status).toBe("success");
  });

  it("queries hit rate via GET /stats/hit-rate", async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({ hit_rate: 0.65, decided: 20, totals: { win: 13, loss: 7 } }),
    });

    const res = await api.getHitRate();
    expect(res.hit_rate).toBe(0.65);
    expect(res.decided).toBe(20);
  });

  it("checks batch availability via POST /availability/check-batch", async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: () =>
        Promise.resolve({
          badges: [{ player: "Saka", market: "shots", line: 2.5, status: "available", platform: "prizepicks" }],
          fallback_mode: false,
        }),
    });

    const res = await api.checkAvailabilityBatch([{ player: "Saka", market: "shots", line: 2.5 }]);
    expect(res.badges[0].status).toBe("available");
  });
});
