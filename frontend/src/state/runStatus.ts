export type RunBadgeColor = "success" | "warning" | "error" | "default" | "info";

export type RunState = {
  label: string;
  color: RunBadgeColor;
  terminal: boolean;
  hasRecommendations: boolean;
};

const ACTIVE = new Set(["pending", "queued", "running"]);

/** Interpret execution lifecycle separately from the recommendation result. */
export function runState(run: { status?: string | null; outcome?: string | null }): RunState {
  const status = (run.status || "unknown").toLowerCase();
  const outcome = (run.outcome || "").toLowerCase();
  if (ACTIVE.has(status)) return { label: status, color: "info", terminal: false, hasRecommendations: false };
  if (status === "interrupted") return { label: "Interrupted - resume available", color: "warning", terminal: true, hasRecommendations: true };
  if (status === "failed" || outcome === "failed") return { label: "Failed", color: "error", terminal: true, hasRecommendations: false };
  if (outcome === "no_picks" || status === "no_picks") return { label: "No verified picks", color: "info", terminal: true, hasRecommendations: false };
  if (status === "partial" || outcome === "partial") return { label: "Partial results", color: "warning", terminal: true, hasRecommendations: true };
  if (status === "success" || outcome === "success") return { label: "Recommendations ready", color: "success", terminal: true, hasRecommendations: true };
  return { label: status, color: "default", terminal: true, hasRecommendations: false };
}
