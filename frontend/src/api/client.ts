import {
  AvailabilityCheckResponse,
  BatchAvailabilityResponse,
  CatalogEventItem,
  CatalogHealthSummary,
  CatalogRefreshJob,
  CatalogSnapshotItem,
  CatalogSportSetting,
  CreatePickPayload,
  CreateSlatePayload,
  DiagnosticDetailResponse,
  DiagnosticOperation,
  HitRateSummary,
  MatchDiscoveryRequest,
  MatchDiscoveryResponse,
  OutcomeRecord,
  PickDetail,
  PickSummary,
  SlateDetail,
} from "./types";

const getApiBase = () => {
  const custom = typeof window !== "undefined" ? localStorage.getItem("COLMILLO_API_URL") : null;
  return custom ? custom.replace(/\/$/, "") : "";
};

const getApiKey = () =>
  (typeof window !== "undefined" ? localStorage.getItem("COLMILLO_API_KEY") : null) ||
  (import.meta.env.VITE_API_KEY as string | undefined) ||
  "";

async function request<T>(endpoint: string, options: RequestInit = {}): Promise<T> {
  const headers = new Headers(options.headers || {});
  headers.set("Content-Type", "application/json");
  const apiKey = getApiKey();
  if (apiKey) {
    headers.set("X-API-Key", apiKey);
  }

  const response = await fetch(`${getApiBase()}${endpoint}`, {
    ...options,
    headers,
  });

  if (!response.ok) {
    let errorDetail = `HTTP ${response.status}: ${response.statusText}`;
    try {
      const json = await response.json();
      if (json.detail) {
        errorDetail = typeof json.detail === "string" ? json.detail : JSON.stringify(json.detail);
      }
    } catch {
      // Keep default error text
    }
    throw new Error(errorDetail);
  }

  return response.json();
}

async function requestBlob(endpoint: string): Promise<Blob> {
  const headers = new Headers();
  const apiKey = getApiKey();
  if (apiKey) {
    headers.set("X-API-Key", apiKey);
  }

  const response = await fetch(`${getApiBase()}${endpoint}`, {
    headers,
  });

  if (!response.ok) {
    let errorDetail = `HTTP ${response.status}: ${response.statusText}`;
    try {
      const json = await response.json();
      if (json.detail) errorDetail = typeof json.detail === "string" ? json.detail : JSON.stringify(json.detail);
    } catch {
      // Keep default error text
    }
    throw new Error(errorDetail);
  }

  return response.blob();
}

export const api = {
  // --- Screen 1: Generate Pick Report ---
  discoverMatches: (payload: MatchDiscoveryRequest) =>
    request<MatchDiscoveryResponse>("/matches/discover", {
      method: "POST",
      body: JSON.stringify(payload),
    }),

  discardDiscoveryCache: (payload: MatchDiscoveryRequest) =>
    request<{ discarded: boolean }>("/matches/discover/cache", {
      method: "DELETE",
      body: JSON.stringify(payload),
    }),

  createPick: (payload: CreatePickPayload) =>
    request<{ id: string; status: string; created_at: string; operation_id?: string }>("/picks", {
      method: "POST",
      body: JSON.stringify(payload),
    }),

  getPick: (pickId: string) =>
    request<PickDetail>(`/picks/${pickId}`),

  getPickStatus: (pickId: string) =>
    request<{ id: string; status: string; error_stage?: string; error_message?: string }>(`/picks/${pickId}/status`),

  checkAvailability: (pickId: string, platforms: string[] = ["prizepicks"]) =>
    request<AvailabilityCheckResponse>(`/picks/${pickId}/availability`, {
      method: "POST",
      body: JSON.stringify({ platforms }),
    }),

  checkAvailabilityBatch: (candidates: any[], platforms: string[] = ["prizepicks"]) =>
    request<BatchAvailabilityResponse>("/availability/check-batch", {
      method: "POST",
      body: JSON.stringify({ candidates, platforms }),
    }),

  // --- Screen 2: Pick History & Outcomes Grading ---
  listPicks: (limit: number = 20, offset: number = 0, sport?: string) => {
    let query = `/picks?limit=${limit}&offset=${offset}`;
    if (sport && sport !== "all") {
      query += `&sport=${sport.toLowerCase()}`;
    }
    return request<{ items: PickSummary[]; limit: number; offset: number }>(query);
  },

  getOutcomes: (pickId: string) =>
    request<{ pick_id: string; items: OutcomeRecord[] }>(`/picks/${pickId}/outcomes`),

  recordOutcomes: (pickId: string, outcomes: OutcomeRecord[]) =>
    request<{ pick_id: string; items: OutcomeRecord[] }>(`/picks/${pickId}/outcomes`, {
      method: "POST",
      body: JSON.stringify({ outcomes }),
    }),

  getHitRate: (since?: string) => {
    const query = since ? `/stats/hit-rate?since=${encodeURIComponent(since)}` : "/stats/hit-rate";
    return request<HitRateSummary>(query);
  },

  // --- Screen 3: Best Today (Slate) ---
  createSlate: (payload: CreateSlatePayload) =>
    request<{ id: string; status: string; created_at: string; operation_id?: string }>("/slates", {
      method: "POST",
      body: JSON.stringify(payload),
    }),

  listSlates: (limit: number = 10, offset: number = 0) =>
    request<{ items: SlateDetail[]; limit: number; offset: number }>(
      `/slates?limit=${limit}&offset=${offset}`
    ),

  getSlate: (slateId: string) =>
    request<SlateDetail>(`/slates/${slateId}`),

  getSlateStatus: (slateId: string) =>
    request<{ id: string; status: string; error_stage?: string; error_message?: string }>(`/slates/${slateId}/status`),

  // --- Screen 4: Grounding Audit ---
  runGroundingAudit: (payload: { num_players: number; num_attempts: number; use_bible_style: boolean }) =>
    request<{
      summary: { avg_field_fill_rate: number; avg_source_url_presence: number; avg_critical_null_rate: number };
      players: Array<{
        player: string;
        fill_rate: number;
        source_urls_presence: number;
        critical_nulls: number;
        confidence_score: number;
        consistency_cv: number;
      }>;
      sources: Array<{ domain: string; count: number }>;
      bible_expected: Array<{ source: string; present: boolean }>;
    }>("/enrichment/audit", {
      method: "POST",
      body: JSON.stringify(payload),
    }),

  // --- Screen 5: Diagnostics & Observability ---
  listDiagnostics: (params: { sport?: string; outcome?: string; service?: string; operation_id?: string; since?: string; limit?: number; offset?: number }) => {
    const q = new URLSearchParams();
    if (params.sport && params.sport !== "all") q.append("sport", params.sport);
    if (params.outcome) q.append("outcome", params.outcome);
    if (params.service) q.append("service", params.service);
    if (params.operation_id) q.append("operation_id", params.operation_id);
    if (params.since) q.append("since", params.since);
    if (params.limit) q.append("limit", params.limit.toString());
    if (params.offset) q.append("offset", params.offset.toString());
    return request<{ items: DiagnosticOperation[]; limit: number; offset: number }>(`/diagnostics/operations?${q.toString()}`);
  },

  getDiagnosticDetail: (operationId: string) =>
    request<DiagnosticDetailResponse>(`/diagnostics/operations/${encodeURIComponent(operationId)}`),

  exportDiagnostic: (operationId: string) =>
    requestBlob(`/diagnostics/operations/${encodeURIComponent(operationId)}/export`),

  getDiagnosticHealth: () =>
    request<{ healthy: boolean; counters?: Record<string, number>; queue_depth?: number }>("/diagnostics/health"),

  // --- Screen 6: Catalog Explorer ---
  listCatalogEvents: (params: { sport?: string; start_from?: string; start_to?: string; limit?: number; offset?: number }) => {
    const q = new URLSearchParams();
    if (params.sport && params.sport !== "all") q.append("sport", params.sport);
    if (params.start_from) q.append("start_from", params.start_from);
    if (params.start_to) q.append("start_to", params.start_to);
    if (params.limit) q.append("limit", params.limit.toString());
    if (params.offset) q.append("offset", params.offset.toString());
    return request<{ items: CatalogEventItem[]; limit: number; offset: number; catalog?: CatalogHealthSummary }>(
      `/catalog/events?${q.toString()}`
    );
  },

  getCatalogSnapshot: (eventId: string) =>
    request<CatalogSnapshotItem>(`/catalog/events/${encodeURIComponent(eventId)}/snapshot`),

  getCatalogHealth: () =>
    request<CatalogHealthSummary>("/catalog/health"),

  listCatalogSettings: () =>
    request<{ items: CatalogSportSetting[] }>("/catalog/settings"),

  updateCatalogSport: (sport: string, enabled: boolean) =>
    request<{ sport: string; enabled: boolean }>(`/catalog/settings/${encodeURIComponent(sport)}`, {
      method: "PUT",
      body: JSON.stringify({ enabled }),
    }),

  refreshCatalog: (date?: string) =>
    request<{ job_id: string; status: "queued"; run_date: string }>("/catalog/refresh", {
      method: "POST",
      body: JSON.stringify(date ? { date } : {}),
    }),

  getCatalogJob: (jobId: string) =>
    request<CatalogRefreshJob>(`/catalog/jobs/${encodeURIComponent(jobId)}`),

  // --- System Health ---
  getHealth: () =>
    request<{ status: string; version: string; channel: string; commit: string; build_time: string }>("/healthz"),
};
