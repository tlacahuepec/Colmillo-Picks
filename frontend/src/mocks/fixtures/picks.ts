import {
  AvailabilityCheckResponse,
  DiscoveredMatch,
  MatchDiscoveryResponse,
  PickDetail,
} from "../../api/types";

export const mockDiscoveredMatches: Record<string, { matches: DiscoveredMatch[]; error?: string }> = {
  soccer: {
    matches: [
      {
        sport: "soccer",
        home_team: "Arsenal",
        away_team: "Liverpool",
        event_date: "2026-09-13",
        league: "Premier League",
        importance: "High",
        kickoff_utc: "2026-09-13T16:30:00Z",
        data_quality: {
          confidence: "high",
          source_count: 3,
        },
      },
    ],
  },
  basketball: {
    matches: [
      {
        sport: "basketball",
        home_team: "Boston Celtics",
        away_team: "LA Lakers",
        event_date: "2026-09-13",
        league: "NBA",
        importance: "Medium",
        kickoff_utc: "2026-09-13T23:00:00Z",
        data_quality: {
          confidence: "high",
          source_count: 2,
        },
      },
    ],
  },
  baseball: {
    matches: [
      {
        sport: "baseball",
        home_team: "New York Yankees",
        away_team: "Boston Red Sox",
        event_date: "2026-09-13",
        league: "MLB",
        importance: "High",
        kickoff_utc: "2026-09-13T18:05:00Z",
        data_quality: {
          confidence: "high",
          source_count: 2,
        },
      },
    ],
  },
  nfl: {
    matches: [
      {
        sport: "nfl",
        home_team: "Kansas City Chiefs",
        away_team: "Buffalo Bills",
        event_date: "2026-09-13",
        league: "NFL",
        importance: "High",
        kickoff_utc: "2026-09-13T20:20:00Z",
        data_quality: {
          confidence: "high",
          source_count: 4,
        },
      },
    ],
  },
};

export const mockDiscoveryResponse: MatchDiscoveryResponse = {
  date_utc: "2026-09-13",
  generated_at_utc: "2026-09-13T12:00:00Z",
  limit_per_sport: 3,
  results: mockDiscoveredMatches,
};

export const mockCreatePickResponse = {
  id: "pick-test-123",
  status: "queued",
  created_at: "2026-09-13T12:00:00Z",
  operation_id: "op-test-123",
};

export const mockPickDetailSuccess: PickDetail = {
  id: "pick-test-123",
  created_at: "2026-09-13T12:00:00Z",
  match_query: "Arsenal vs Liverpool",
  display_title: "Arsenal vs Liverpool",
  sport: "soccer",
  status: "success",
  outcome: "success",
  latency_ms: 1250,
  operation_id: "op-test-123",
  report_markdown: "# Match Pick Report: Arsenal vs Liverpool\n\n- **Bukayo Saka**: Over 2.5 Shots (Score: 88)\n- **Mohamed Salah**: Over 1.5 Shots on Target (Score: 84)",
  scores: [
    {
      rank: 1,
      player: "Bukayo Saka",
      market: "shots",
      line: 2.5,
      direction: "over",
      confidence: "high",
      normalized_score: 88.5,
      odds: "1.85",
      sportsbook: "bet365",
      risk_flags: ["away_form"],
    },
    {
      rank: 2,
      player: "Mohamed Salah",
      market: "shots_on_target",
      line: 1.5,
      direction: "over",
      confidence: "medium",
      normalized_score: 84.0,
      odds: "1.90",
      sportsbook: "fanduel",
      risk_flags: [],
    },
  ],
  trace: {
    stages_completed: ["discovery", "feature_engineering", "scoring", "report"],
  },
  match_inputs: {
    home_team: "Arsenal",
    away_team: "Liverpool",
    event_date: "2026-09-13",
    sport: "soccer",
  },
};

export const mockPickDetailFailed: PickDetail = {
  id: "pick-test-failed",
  created_at: "2026-09-13T12:00:00Z",
  match_query: "Arsenal vs Liverpool",
  display_title: "Arsenal vs Liverpool",
  sport: "soccer",
  status: "failed",
  error_stage: "feature_engineering",
  error_message: "Failed to fetch historical stats for players",
  operation_id: "op-test-failed",
};

export const mockAvailabilityResponse: AvailabilityCheckResponse = {
  pick_id: "pick-test-123",
  fallback_mode: false,
  fallback_reason: "",
  checked_at: "2026-09-13T12:00:05Z",
  badges: [
    {
      player: "Bukayo Saka",
      market: "shots",
      line: 2.5,
      status: "available",
      platform: "prizepicks",
      platform_line: 2.5,
      url: "https://app.prizepicks.com",
      last_checked: "2026-09-13T12:00:05Z",
    },
    {
      player: "Mohamed Salah",
      market: "shots_on_target",
      line: 1.5,
      status: "available",
      platform: "prizepicks",
      platform_line: 2.0, // Line differs!
      url: "https://app.prizepicks.com",
      last_checked: "2026-09-13T12:00:05Z",
    },
    {
      player: "Kai Havertz",
      market: "fouls",
      line: 1.5,
      status: "unavailable",
      platform: "prizepicks",
      platform_line: null,
      last_checked: "2026-09-13T12:00:05Z",
    },
  ],
};
