import { describe, expect, it } from "vitest";
import { runState } from "./runStatus";

describe("runState", () => {
  it("does not present completed no-pick work as recommendation success", () => {
    expect(runState({ status: "success", outcome: "no_picks" })).toMatchObject({ label: "No verified picks", terminal: true, hasRecommendations: false });
  });

  it("preserves partial and legacy success semantics", () => {
    expect(runState({ status: "success", outcome: "partial" })).toMatchObject({ label: "Partial results", color: "warning", hasRecommendations: true });
    expect(runState({ status: "success" })).toMatchObject({ label: "Recommendations ready", color: "success" });
  });
});
