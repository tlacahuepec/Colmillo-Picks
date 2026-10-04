export type Sport = "soccer" | "basketball" | "baseball" | "nfl";

export interface PickSummary {
  id: string;
  created_at: string;
  match_query: string;
  display_title: string;
  status: string;
  sport?: string;
  competition?: string;
  fixture_status?: string;
  llm_status?: string;
  operation_id?: string;
  outcome?: string;
  latency_ms?: number | null;
  error_stage?: string | null;
}

export interface PickScore {
  rank?: number;
  player?: string;
  name?: string;
  subject_name?: string;
  subject_type?: string;
  market?: string;
  prop?: string;
  line?: number;
  direction?: "over" | "under" | string;
  confidence?: number | string;
  normalized_score?: number;
  odds?: string | number;
  sportsbook?: string;
  risk_flags?: string[];
  availability_status?: string;
  llm_rationale?: string;
  rationale?: string;
  factors?: Record<string, any>;
  grounding_sources?: Array<{ title?: string; url?: string }>;
}

export interface PickDetail {
  id: string;
  created_at: string;
  match_query: string;
  display_title: string;
  status: "queued" | "running" | "success" | "partial" | "failed" | "no_picks";
  sport?: string;
  operation_id?: string;
  outcome?: string;
  latency_ms?: number | null;
  error_stage?: string;
  error_message?: string;
  error_details?: Record<string, any>;
  report_markdown?: string;
  scores?: PickScore[];
  trace?: Record<string, any>;
  request?: Record<string, any>;
  match_inputs?: Record<string, any>;
}

export interface CreatePickPayload {
  sport: string;
  event_date: string;
  home_team: string;
  away_team: string;
  top_n: number;
  use_llm_enrichment?: boolean;
  use_llm?: boolean;
  allow_deterministic_fallback?: boolean;
  markets?: string[];
  league?: string;
  timezone?: string;
}

export interface DiscoverySource {
  label: string;
  url?: string | null;
  grounded?: boolean;
}

export interface DiscoveredMatch {
  sport: string;
  home_team: string;
  away_team: string;
  event_date: string;
  league?: string;
  competition?: string;
  kickoff_utc?: string;
  importance: string;
  notes?: string;
  source_provider?: string;
  source_model?: string;
  sources?: DiscoverySource[];
  data_quality?: {
    confidence?: string;
    missing_fields?: string[];
    source_count?: number;
    status?: "verified" | "empty" | "unavailable" | "error" | "partial" | string;
    verified_count?: number;
    rejected_counts?: Record<string, number>;
    reason?: string;
    [key: string]: any;
  };
}

export interface SportDiscoveryResult {
  matches: DiscoveredMatch[];
  error?: string;
  data_quality?: {
    status?: "verified" | "empty" | "unavailable" | "error" | "partial" | string;
    verified_count?: number;
    rejected_counts?: Record<string, number>;
    reason?: string;
    [key: string]: any;
  };
}

export interface MatchDiscoveryRequest {
  date: string;
  sports: string[];
  limit_per_sport: number;
  llm_provider?: string;
  llm_model?: string;
  timezone?: string;
  force_refresh?: boolean;
}

export interface MatchDiscoveryResponse {
  date_utc: string;
  generated_at_utc: string;
  limit_per_sport: number;
  results: Record<string, SportDiscoveryResult>;
  cache_status?: "cached" | "refreshed" | "uncached";
  cache_confidence?: string;
  cache_expires_at?: string;
}

export interface AvailabilityBadge {
  player: string;
  market: string;
  line: number;
  status: string; // "available" | "unavailable" | "unknown"
  platform: string;
  platform_line?: number | null;
  url?: string | null;
  last_checked?: string;
}

export interface AvailabilityCheckResponse {
  pick_id: string;
  badges: AvailabilityBadge[];
  fallback_mode: boolean;
  fallback_reason?: string;
  checked_at?: string;
}

export interface BatchAvailabilityResponse {
  badges: AvailabilityBadge[];
  fallback_mode: boolean;
  fallback_reason?: string;
  checked_at?: string;
}

export interface SlateRankedCandidate {
  rank: number;
  sport: string;
  player?: string;
  subject_name?: string;
  subject_type?: string;
  selection?: string;
  market: string;
  line?: number;
  direction?: string;
  confidence: string | number;
  normalized_score: number;
  risk_flags: string[];
  availability_status?: string;
  source_match: {
    home_team?: string;
    away_team?: string;
    event_date?: string;
    kickoff_utc?: string;
    catalog_source?: string;
    catalog_refresh_resources?: string[];
  };
  source_pick?: Record<string, any>;
  offer?: Record<string, any>;
}

export interface SlateMatchRun {
  sport: string;
  home_team: string;
  away_team: string;
  event_date: string;
  status: string;
  pick_count: number;
  latency_ms?: number | null;
  catalog_source?: string;
  catalog_refresh_resources?: string[];
  error_stage?: string;
  error_message?: string;
}

export interface SlateSummary {
  id: string;
  created_at: string;
  status: "pending" | "queued" | "running" | "success" | "partial" | "failed";
  outcome?: string;
  operation_id?: string | null;
  request: Record<string, any>;
  latency_ms?: number | null;
}

export interface SlateDetail extends SlateSummary {
  candidates: SlateRankedCandidate[];
  match_runs: SlateMatchRun[];
  discovery_latency_ms?: number | null;
  matches_attempted?: number | null;
  matches_succeeded?: number | null;
  prompt_tokens?: number;
  completion_tokens?: number;
  total_tokens?: number;
  error_stage?: string;
  error_message?: string;
}

export interface SlateStatus {
  id: string;
  status: SlateSummary["status"];
  operation_id?: string | null;
  outcome?: string;
  error_stage?: string | null;
  error_message?: string | null;
  latency_ms?: number | null;
}

export interface SlateListResponse {
  items: SlateSummary[];
  limit: number;
  offset: number;
}

export interface CreateSlatePayload {
  date: string;
  sports: string[];
  max_matches_per_sport: number;
  top_n: number;
  nfl_market_group?: "all" | "player_props" | "game_bets";
  timezone?: string;
}

export interface OutcomeRecord {
  rank: number;
  player: string;
  market: string;
  result: "win" | "loss" | "push" | "void";
  recorded_at?: string;
}

export interface HitRateSummary {
  hit_rate?: number;
  decided: number;
  totals: {
    win: number;
    loss: number;
    push?: number;
    void?: number;
  };
}

export interface DiagnosticOperation {
  operation_id: string;
  service: string;
  sport?: string;
  home_team?: string;
  away_team?: string;
  outcome: string;
  duration_ms?: number;
  started_at: string;
  updated_at: string;
  summary?: string;
  events?: DiagnosticEvent[];
  metadata?: Record<string, any>;
}

export interface DiagnosticCompleteness {
  status: string;
  complete: boolean;
  events_returned: number;
  has_more: boolean;
  truncated: boolean;
  offset: number;
  limit: number;
  scope: string;
  snapshot: boolean;
  retention_may_apply: boolean;
}

export interface DiagnosticDetailResponse {
  operation: DiagnosticOperation;
  events: DiagnosticEvent[];
  completeness: DiagnosticCompleteness;
}

export interface DiagnosticListResponse {
  items: DiagnosticOperation[];
  limit: number;
  offset: number;
  has_more: boolean;
  next_offset: number | null;
}

export interface DiagnosticEventsResponse {
  items: DiagnosticEvent[];
  limit: number;
  offset: number;
  completeness: DiagnosticCompleteness;
}

/** The API serializes event time as `ts`; `timestamp` remains for legacy data. */
export interface DiagnosticEvent {
  event: string;
  stage?: string;
  level: string;
  duration_ms?: number;
  ts?: string;
  timestamp?: string;
  outcome?: string;
  metadata?: Record<string, any>;
}

export interface CatalogEventItem {
  event_id: string;
  sport: string;
  league: string;
  start_time: string;
  status: string;
  home_team?: CatalogCanonicalRef;
  away_team?: CatalogCanonicalRef;
}

export interface CatalogCanonicalRef {
  entity_type: string;
  canonical_id: string;
  display_name?: string | null;
  provider_ids?: Record<string, string>;
}

export interface CatalogSportSetting {
  sport: string;
  enabled: boolean;
  discovered_at: string;
  updated_at: string;
  retained_events: number;
}

export interface CatalogSnapshotItem {
  snapshot_id: string;
  event_id: string;
  created_at: string;
  as_of: string;
  completeness: string;
  normalization_version: string;
  payload: Record<string, any>;
}

export interface CatalogHealthSummary {
  available: boolean;
  path: string;
  events: number;
  snapshots: number;
  observations: number;
  jobs_by_state?: Record<string, number>;
  raw_archives?: number;
}

export interface CatalogRefreshJob {
  job_id: string;
  run_date: string;
  state: "running" | "success" | "partial" | "failed" | "interrupted";
  checkpoint?: string | null;
  summary?: Record<string, number> | string | null;
}
