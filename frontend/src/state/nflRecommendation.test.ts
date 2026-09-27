import { describe, expect, it } from "vitest";
import { pickNflRecommendationSummary } from "./nflRecommendation";

describe("pickNflRecommendationSummary", () => {
  it("uses a persisted run summary before failure details", () => {
    expect(pickNflRecommendationSummary({ match_inputs: { recommendation_summary: { code: "offers_unavailable", message: "No offers." } } })).toMatchObject({ code: "offers_unavailable" });
  });

  it("reads a failed NFL run's public error details", () => {
    expect(pickNflRecommendationSummary({ error_details: { reason: { recommendation_summary: { code: "provider_failure", message: "Retry." } } } })).toMatchObject({ code: "provider_failure" });
  });
});
