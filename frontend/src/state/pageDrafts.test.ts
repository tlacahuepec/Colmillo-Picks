import { afterEach, describe, expect, it } from "vitest";
import { clearAllPageDrafts, localDay, loadPageDraft, savePageDraft } from "./pageDrafts";

afterEach(() => window.sessionStorage.clear());

describe("page drafts", () => {
  it("uses Chicago's calendar day rather than UTC midnight", () => {
    expect(localDay("America/Chicago", new Date("2026-09-21T00:30:00Z"))).toBe("2026-09-20");
    expect(localDay("America/Chicago", new Date("2026-09-21T06:30:00Z"))).toBe("2026-09-21");
  });

  it("hydrates a versioned draft across a remount", () => {
    savePageDraft("generate", { team: "Bears", sport: "NFL" });

    const restored = loadPageDraft(
      "generate",
      { team: "", sport: "Soccer" },
      (value): value is { team: string; sport: string } => typeof value === "object" && value !== null && typeof (value as { team?: unknown }).team === "string" && typeof (value as { sport?: unknown }).sport === "string",
    );

    expect(restored).toEqual({ team: "Bears", sport: "NFL" });
  });

  it("drops malformed and obsolete drafts rather than blocking a page", () => {
    window.sessionStorage.setItem("colmillo:view-draft:history", "not-json");
    expect(loadPageDraft("history", { page: 0 }, (value): value is { page: number } => typeof value === "object" && value !== null && typeof (value as { page?: unknown }).page === "number")).toEqual({ page: 0 });
    expect(window.sessionStorage.getItem("colmillo:view-draft:history")).toBeNull();
  });

  it("only clears Colmillo draft keys", () => {
    savePageDraft("catalog", { sport: "nfl" });
    window.sessionStorage.setItem("unrelated", "keep");
    clearAllPageDrafts();
    expect(window.sessionStorage.getItem("colmillo:view-draft:catalog")).toBeNull();
    expect(window.sessionStorage.getItem("unrelated")).toBe("keep");
  });
});
