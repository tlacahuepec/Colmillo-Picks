export interface NflRecommendationSummary { code: string; message: string; counts?: Record<string, number>; }

export function nflRecommendationSummary(value?: Record<string, any>): NflRecommendationSummary | null {
  const summary = value?.recommendation_summary;
  return summary && typeof summary.code === "string" && typeof summary.message === "string" ? summary as NflRecommendationSummary : null;
}

export function pickNflRecommendationSummary(pick: { match_inputs?: Record<string, any>; error_details?: Record<string, any> }): NflRecommendationSummary | null {
  return nflRecommendationSummary(pick.match_inputs) || nflRecommendationSummary(pick.error_details?.reason);
}
