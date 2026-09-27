import React, { useEffect, useRef, useState } from "react";
import {
  Box,
  Card,
  Typography,
  Button,
  Chip,
  TextField,
  Select,
  MenuItem,
  FormControl,
  InputLabel,
  Slider,
  FormControlLabel,
  Checkbox,
  LinearProgress,
  Alert,
  Accordion,
  AccordionSummary,
  AccordionDetails,
  CircularProgress,
  Divider,
  Paper,
} from "@mui/material";
import {
  Target,
  Zap,
  Clock,
  ExternalLink,
  ChevronDown,
  CheckCircle2,
  AlertTriangle,
  XCircle,
  HelpCircle,
  Activity,
  Play,
} from "lucide-react";
import { api } from "../api/client";
import {
  AvailabilityBadge,
  DiscoveredMatch,
  MatchDiscoveryResponse,
  PickDetail,
} from "../api/types";
import { MarkdownRenderer } from "../components/Common/MarkdownRenderer";
import { DEFAULT_TIMEZONE, isRecord, loadPageDraft, localDay, savePageDraft } from "../state/pageDrafts";
import { runState } from "../state/runStatus";
import { pickNflRecommendationSummary } from "../state/nflRecommendation";

const BASEBALL_MARKETS = [
  "hits",
  "total_bases",
  "runs",
  "rbi",
  "home_runs",
  "strikeouts",
  "walks",
  "pitcher_outs",
];

const NFL_PLAYER_MARKETS = [
  "passing_yards",
  "passing_touchdowns",
  "interceptions_thrown",
  "rushing_yards",
  "receiving_yards",
  "receptions",
  "anytime_touchdown",
];

const NFL_GAME_MARKETS = ["moneyline", "spread", "total"];
const NFL_ALL_MARKETS = [...NFL_PLAYER_MARKETS, ...NFL_GAME_MARKETS];

const TEAM_HINTS: Record<string, { home: string; away: string }> = {
  soccer: { home: "e.g. Bayern Munich", away: "e.g. Stuttgart" },
  basketball: { home: "e.g. Boston Celtics", away: "e.g. Los Angeles Lakers" },
  baseball: { home: "e.g. New York Yankees", away: "e.g. Boston Red Sox" },
  nfl: { home: "e.g. Kansas City Chiefs", away: "e.g. Buffalo Bills" },
};

function formatUtcToLocal(utcStr?: string | null): string {
  if (!utcStr) return "kickoff unknown";
  try {
    const dt = new Date(utcStr);
    return dt.toLocaleString(undefined, {
      month: "short",
      day: "numeric",
      hour: "numeric",
      minute: "2-digit",
      hour12: true,
    });
  } catch {
    return utcStr;
  }
}

function formatSuggestedMatch(match: DiscoveredMatch): string {
  const sport = (match.sport || "Sport").toUpperCase();
  const home = match.home_team || "Unknown";
  const away = match.away_team || "Unknown";
  const comp = match.competition || match.league || "competition unknown";
  const kickoff = formatUtcToLocal(match.kickoff_utc);
  const importance = match.importance || "importance unknown";
  const dq = match.data_quality || {};
  const conf = dq.confidence || "unknown";
  const missing = dq.missing_fields && dq.missing_fields.length > 0 ? dq.missing_fields.join(",") : "none";
  const sources = dq.source_count ?? (match.sources ? match.sources.length : 0);

  return `${sport} | ${home} vs ${away} | ${comp} | ${kickoff} | importance=${importance} | confidence=${conf} | missing=${missing} | sources=${sources}`;
}

interface GeneratePageProps {
  onNavigateToDiagnostics?: (operationId: string) => void;
}

type GenerateDraft = {
  savedOn: string; discoverDate: string; discoverSports: string[]; discoverLimit: number;
  suggestionTopN: number; suggestionExplain: boolean; suggestionFallback: boolean; suggestionFireForget: boolean;
  sport: string; nflGroup: string; matchDate: string; homeTeam: string; awayTeam: string;
  selectedBaseballMarkets: string[]; selectedNflMarkets: string[]; topN: number;
  addExplanations: boolean; allowFallback: boolean; fireAndForget: boolean; availPlatforms: string[]; activePickId: string | null;
};

const newGenerateDraft = (): GenerateDraft => ({
  savedOn: localDay(), discoverDate: localDay(), discoverSports: ["Soccer", "Basketball", "Baseball", "NFL"],
  discoverLimit: 3, suggestionTopN: 5, suggestionExplain: false, suggestionFallback: false, suggestionFireForget: false,
  sport: "Soccer", nflGroup: "All", matchDate: localDay(), homeTeam: "", awayTeam: "",
  selectedBaseballMarkets: BASEBALL_MARKETS, selectedNflMarkets: NFL_ALL_MARKETS, topN: 10,
  addExplanations: false, allowFallback: false, fireAndForget: false, availPlatforms: ["prizepicks"], activePickId: null,
});

const isGenerateDraft = (value: unknown): value is GenerateDraft => isRecord(value)
  && typeof value.savedOn === "string" && typeof value.discoverDate === "string"
  && Array.isArray(value.discoverSports) && typeof value.sport === "string";

export const GeneratePage: React.FC<GeneratePageProps> = ({ onNavigateToDiagnostics }) => {
  const [initialDraft] = useState(() => {
    const draft = loadPageDraft("generate", newGenerateDraft(), isGenerateDraft);
    return draft.savedOn === localDay() ? draft : newGenerateDraft();
  });
  // ---- Match Suggestions State ----
  const [discoverDate, setDiscoverDate] = useState<string>(initialDraft.discoverDate);
  const [discoverSports, setDiscoverSports] = useState<string[]>(initialDraft.discoverSports);
  const [discoverLimit, setDiscoverLimit] = useState<number>(initialDraft.discoverLimit);
  const [suggestionTopN, setSuggestionTopN] = useState<number>(initialDraft.suggestionTopN);
  const [suggestionExplain, setSuggestionExplain] = useState<boolean>(initialDraft.suggestionExplain);
  const [suggestionFallback, setSuggestionFallback] = useState<boolean>(initialDraft.suggestionFallback);
  const [suggestionFireForget, setSuggestionFireForget] = useState<boolean>(initialDraft.suggestionFireForget);
  const [discovering, setDiscovering] = useState<boolean>(false);
  const [discoveryResults, setDiscoveryResults] = useState<MatchDiscoveryResponse | null>(null);
  const [discoveryError, setDiscoveryError] = useState<string | null>(null);

  // ---- Manual Pick Form State ----
  const [sport, setSport] = useState<string>(initialDraft.sport);
  const [nflGroup, setNflGroup] = useState<string>(initialDraft.nflGroup);
  const [matchDate, setMatchDate] = useState<string>(initialDraft.matchDate);
  const [homeTeam, setHomeTeam] = useState<string>(initialDraft.homeTeam);
  const [awayTeam, setAwayTeam] = useState<string>(initialDraft.awayTeam);
  const [selectedBaseballMarkets, setSelectedBaseballMarkets] = useState<string[]>(initialDraft.selectedBaseballMarkets);
  const [selectedNflMarkets, setSelectedNflMarkets] = useState<string[]>(initialDraft.selectedNflMarkets);
  const [topN, setTopN] = useState<number>(initialDraft.topN);
  const [addExplanations, setAddExplanations] = useState<boolean>(initialDraft.addExplanations);
  const [allowFallback, setAllowFallback] = useState<boolean>(initialDraft.allowFallback);
  const [fireAndForget, setFireAndForget] = useState<boolean>(initialDraft.fireAndForget);

  // ---- Pipeline Execution State ----
  const [executing, setExecuting] = useState<boolean>(false);
  const [statusMessage, setStatusMessage] = useState<string>("");
  const [currentPickId, setCurrentPickId] = useState<string | null>(initialDraft.activePickId || null);
  const [pickResult, setPickResult] = useState<PickDetail | null>(null);
  const [pipelineError, setPipelineError] = useState<string | null>(null);
  const [fireAndForgetSuccess, setFireAndForgetSuccess] = useState<{ pickId: string; operationId?: string } | null>(null);

  // ---- Availability State ----
  const [availBadges, setAvailBadges] = useState<AvailabilityBadge[]>([]);
  const [checkingAvail, setCheckingAvail] = useState<boolean>(false);
  const [availFallbackNotice, setAvailFallbackNotice] = useState<string | null>(null);
  const [availPlatforms, setAvailPlatforms] = useState<string[]>(initialDraft.availPlatforms);

  useEffect(() => {
    savePageDraft("generate", { savedOn: localDay(), discoverDate, discoverSports, discoverLimit, suggestionTopN,
      suggestionExplain, suggestionFallback, suggestionFireForget, sport, nflGroup, matchDate, homeTeam, awayTeam,
      selectedBaseballMarkets, selectedNflMarkets, topN, addExplanations, allowFallback, fireAndForget, availPlatforms,
      activePickId: currentPickId });
  }, [discoverDate, discoverSports, discoverLimit, suggestionTopN, suggestionExplain, suggestionFallback,
    suggestionFireForget, sport, nflGroup, matchDate, homeTeam, awayTeam, selectedBaseballMarkets,
    selectedNflMarkets, topN, addExplanations, allowFallback, fireAndForget, availPlatforms, currentPickId]);

  // Dynamic hints
  const currentHints = TEAM_HINTS[sport.toLowerCase()] || { home: "", away: "" };

  const handleSportChange = (newSport: string) => {
    setSport(newSport);
    if (newSport.toLowerCase() === "baseball") {
      setSelectedBaseballMarkets(BASEBALL_MARKETS);
    } else if (newSport === "NFL") {
      setSelectedNflMarkets(
        nflGroup === "Player props"
          ? NFL_PLAYER_MARKETS
          : nflGroup === "Game bets"
          ? NFL_GAME_MARKETS
          : NFL_ALL_MARKETS
      );
    }
  };

  // Sync NFL market options with nflGroup
  const handleNflGroupChange = (group: string) => {
    setNflGroup(group);
    if (group === "Player props") setSelectedNflMarkets(NFL_PLAYER_MARKETS);
    else if (group === "Game bets") setSelectedNflMarkets(NFL_GAME_MARKETS);
    else setSelectedNflMarkets(NFL_ALL_MARKETS);
  };

  // ---- Discovery Handler ----
  const handleDiscoverMatches = async (forceRefresh = false) => {
    setDiscovering(true);
    setDiscoveryError(null);
    try {
      const resp = await api.discoverMatches({
        date: discoverDate,
        sports: discoverSports.map((s) => s.toLowerCase()),
        limit_per_sport: discoverLimit,
        timezone: DEFAULT_TIMEZONE,
        force_refresh: forceRefresh,
      });
      setDiscoveryResults(resp);
    } catch (err: any) {
      setDiscoveryError(err.message || "Match discovery failed");
    } finally {
      setDiscovering(false);
    }
  };

  const handleDiscardDiscoveryCache = async () => {
    setDiscoveryError(null);
    try {
      await api.discardDiscoveryCache({
        date: discoverDate,
        sports: discoverSports.map((s) => s.toLowerCase()),
        limit_per_sport: discoverLimit,
        timezone: DEFAULT_TIMEZONE,
      });
      setDiscoveryResults(null);
    } catch (err: any) {
      setDiscoveryError(err.message || "Could not discard cached suggestions");
    }
  };

  // ---- Use Suggested Match in Manual Form ----
  const handleUseMatch = (match: DiscoveredMatch) => {
    const s = (match.sport || "").toLowerCase();
    let mappedSport = "Soccer";
    if (s === "basketball") mappedSport = "Basketball";
    else if (s === "baseball") mappedSport = "Baseball";
    else if (s === "nfl") mappedSport = "NFL";

    handleSportChange(mappedSport);
    setMatchDate(match.event_date);
    setHomeTeam(match.home_team);
    setAwayTeam(match.away_team);
  };

  // ---- Submit and Poll Helper ----
  const submitAndPoll = async (payload: any, wait: boolean) => {
    setExecuting(true);
    setPipelineError(null);
    setPickResult(null);
    setFireAndForgetSuccess(null);
    setAvailBadges([]);
    setAvailFallbackNotice(null);
    setStatusMessage("Submitting pick request to pipeline...");

    try {
      const accepted = await api.createPick(payload);
      const pickId = accepted.id;
      setCurrentPickId(pickId);

      if (!wait) {
        setStatusMessage(
          `Pick ${pickId} submitted. Pipeline is running in the background — check Pick History when ready.`
        );
        setFireAndForgetSuccess({
          pickId,
          operationId: accepted.operation_id,
        });
        setExecuting(false);
        return;
      }

      setStatusMessage(`Pick ${pickId} accepted. Waiting for pipeline to finish...`);
    } catch (err: any) {
      setPipelineError(err.message || "Failed to submit pick");
      setExecuting(false);
    }
  };

  // ---- Run Suggested Match ----
  const handleRunSuggested = (match: DiscoveredMatch) => {
    const payload = {
      sport: (match.sport || "").toLowerCase(),
      event_date: match.event_date,
      home_team: match.home_team,
      away_team: match.away_team,
      top_n: suggestionTopN,
      use_llm: suggestionExplain,
      allow_deterministic_fallback: suggestionFallback,
      league: match.league || undefined,
    };
    submitAndPoll(payload, !suggestionFireForget);
  };

  // ---- Manual Form Submit ----
  const handleManualSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!homeTeam.trim()) {
      setPipelineError("Home team is required");
      return;
    }
    if (!awayTeam.trim()) {
      setPipelineError("Away team is required");
      return;
    }
    if (sport === "NFL" && selectedNflMarkets.length === 0) {
      setPipelineError("Select at least one NFL market.");
      return;
    }

    const payload: any = {
      sport: sport.toLowerCase(),
      home_team: homeTeam.trim(),
      away_team: awayTeam.trim(),
      event_date: matchDate,
      top_n: topN,
      use_llm: addExplanations,
      allow_deterministic_fallback: allowFallback,
      timezone: DEFAULT_TIMEZONE,
    };

    if (sport.toLowerCase() === "baseball") {
      payload.league = "mlb";
      payload.markets = selectedBaseballMarkets;
    } else if (sport === "NFL") {
      payload.league = "nfl";
      payload.markets = selectedNflMarkets;
    }

    submitAndPoll(payload, !fireAndForget);
  };

  // ---- Availability Fetcher ----
  const fetchAvailability = async (pickId: string, platforms: string[]) => {
    setCheckingAvail(true);
    setAvailFallbackNotice(null);
    try {
      const resp = await api.checkAvailability(pickId, platforms);
      if (resp.fallback_mode) {
        setAvailFallbackNotice(resp.fallback_reason || "Fallback mode active");
      }
      setAvailBadges(resp.badges || []);
    } catch (err: any) {
      setAvailFallbackNotice(`Availability check failed: ${err.message}`);
    } finally {
      setCheckingAvail(false);
    }
  };

  // The accepted ID is persisted, while this observer is deliberately page-scoped.
  // Leaving the page stops network observation; returning reconnects to the same job
  // instead of creating another pick.
  useEffect(() => {
    if (!currentPickId) return;
    let cancelled = false;
    let requestInFlight = false;
    let timer: number | undefined;
    const stop = () => {
      if (timer !== undefined) window.clearInterval(timer);
    };

    const observe = async () => {
      if (cancelled || requestInFlight) return;
      requestInFlight = true;
      try {
        const status = await api.getPickStatus(currentPickId);
        if (cancelled) return;
        if (status.status === "failed") {
          stop();
          setPipelineError(`Pipeline failed at stage ${status.error_stage || "unknown"}: ${status.error_message || "Unknown error"}`);
          setExecuting(false);
          return;
        }
        if (status.status === "success" || status.status === "partial" || status.status === "no_picks") {
          stop();
          const detail = await api.getPick(currentPickId);
          if (cancelled) return;
          setPickResult(detail);
          setExecuting(false);
          if (detail.outcome !== "no_picks") await fetchAvailability(currentPickId, availPlatforms);
          return;
        }
        setExecuting(true);
        setStatusMessage(`Pick ${currentPickId} is ${status.status}. Watching for completion...`);
      } catch {
        if (!cancelled) setStatusMessage(`Connection interrupted while observing ${currentPickId}; retrying automatically...`);
      } finally {
        requestInFlight = false;
      }
    };

    void observe();
    timer = window.setInterval(observe, 2000);
    return () => {
      cancelled = true;
      stop();
    };
  }, [currentPickId, availPlatforms]);

  return (
    <Box sx={{ display: "flex", flexDirection: "column", gap: 3.5, pb: 6 }}>
      {/* Header */}
      <Box>
        <Typography variant="h4" sx={{ fontWeight: 800, letterSpacing: "-0.02em", color: "#FFF" }}>
          Generate Pick Report
        </Typography>
        <Typography variant="body2" sx={{ color: "text.secondary", mt: 0.5 }}>
          Enter match details to generate prop pick recommendations or discover today's scheduled matchups.
        </Typography>
      </Box>

      {/* ========================================================================= */}
      {/* SECTION 1: MATCH SUGGESTIONS (Exact Streamlit Parity)                     */}
      {/* ========================================================================= */}
      <Card sx={{ p: 3, bgcolor: "background.paper", border: "1px solid rgba(255,255,255,0.08)" }}>
        <Typography variant="h6" sx={{ fontWeight: 700, mb: 2, display: "flex", alignItems: "center", gap: 1 }}>
          <Target size={18} color="#06B6D4" />
          Match Suggestions
        </Typography>

        <Box sx={{ display: "grid", gridTemplateColumns: { xs: "1fr", md: "1.2fr 2fr 1.2fr" }, gap: 2, mb: 2 }}>
          <TextField
            type="date"
            label="Suggestion date"
            value={discoverDate}
            onChange={(e) => setDiscoverDate(e.target.value)}
            size="small"
            InputLabelProps={{ shrink: true }}
            fullWidth
          />

          <FormControl fullWidth size="small">
            <InputLabel>Suggestion sports</InputLabel>
            <Select
              multiple
              value={discoverSports}
              onChange={(e: any) => setDiscoverSports(e.target.value)}
              renderValue={(selected) => selected.join(", ")}
              label="Suggestion sports"
            >
              {["Soccer", "Basketball", "Baseball", "NFL"].map((s) => (
                <MenuItem key={s} value={s}>
                  {s}
                </MenuItem>
              ))}
            </Select>
          </FormControl>

          <Box sx={{ px: 1 }}>
            <Typography variant="caption" sx={{ color: "text.secondary" }}>
              Matches per sport: <strong>{discoverLimit}</strong>
            </Typography>
            <Slider
              value={discoverLimit}
              onChange={(_, val) => setDiscoverLimit(val as number)}
              min={1}
              max={10}
              step={1}
              size="small"
              valueLabelDisplay="auto"
            />
          </Box>
        </Box>

        {/* Suggestion Controls Row */}
        <Box sx={{ display: "grid", gridTemplateColumns: { xs: "1fr", sm: "repeat(4, 1fr)" }, gap: 2, alignItems: "center", mb: 2 }}>
          <Box sx={{ px: 1 }}>
            <Typography variant="caption" sx={{ color: "text.secondary" }}>
              Suggestion top N: <strong>{suggestionTopN}</strong>
            </Typography>
            <Slider
              value={suggestionTopN}
              onChange={(_, val) => setSuggestionTopN(val as number)}
              min={1}
              max={10}
              step={1}
              size="small"
              valueLabelDisplay="auto"
            />
          </Box>

          <FormControlLabel
            control={
              <Checkbox
                checked={suggestionExplain}
                onChange={(e) => setSuggestionExplain(e.target.checked)}
                size="small"
              />
            }
            label={<Typography variant="body2">Suggestion explanations</Typography>}
          />

          <FormControlLabel
            control={
              <Checkbox
                checked={suggestionFallback}
                onChange={(e) => setSuggestionFallback(e.target.checked)}
                size="small"
              />
            }
            label={<Typography variant="body2">Suggestion fallback</Typography>}
          />

          <FormControlLabel
            control={
              <Checkbox
                checked={suggestionFireForget}
                onChange={(e) => setSuggestionFireForget(e.target.checked)}
                size="small"
              />
            }
            label={<Typography variant="body2">Fire & forget</Typography>}
          />
        </Box>

        <Box sx={{ display: "flex", gap: 1, flexWrap: "wrap" }}>
          <Button variant="contained" color="primary" onClick={() => handleDiscoverMatches()} disabled={discovering}
            startIcon={discovering ? <CircularProgress size={16} color="inherit" /> : <Zap size={16} />} sx={{ fontWeight: 700, px: 3 }}>
            {discovering ? "Discovering matches..." : "Discover Today's Matches"}
          </Button>
          <Button variant="outlined" onClick={() => handleDiscoverMatches(true)} disabled={discovering}>
            Find New Suggestions
          </Button>
          <Button variant="text" color="warning" onClick={handleDiscardDiscoveryCache} disabled={discovering}>
            Discard Cached Suggestions
          </Button>
        </Box>

        {discoveryResults?.cache_status && (
          <Alert severity="info" sx={{ mt: 2 }}>
            {discoveryResults.cache_status === "cached" ? "Using cached suggestions" : "Fresh suggestions saved"}
            {` (${discoveryResults.cache_confidence || "low"} confidence)`}
            {discoveryResults.cache_expires_at ? ` — expires ${new Date(discoveryResults.cache_expires_at).toLocaleTimeString()}.` : ""}
          </Alert>
        )}

        {discoveryError && (
          <Alert severity="error" sx={{ mt: 2 }}>
            {discoveryError}
          </Alert>
        )}

        {/* Render Discovered Matches Grouped by Sport */}
        {discoveryResults && discoveryResults.results && (
          <Box sx={{ mt: 3, display: "flex", flexDirection: "column", gap: 2.5 }}>
            <Divider sx={{ borderColor: "rgba(255,255,255,0.08)" }} />
            {Object.entries(discoveryResults.results).map(([sportKey, sportData]) => (
              <Box key={sportKey}>
                <Typography variant="subtitle1" sx={{ fontWeight: 800, color: "primary.main", textTransform: "capitalize", mb: 1 }}>
                  {sportKey}
                </Typography>

                {sportData.error && (
                  <Alert severity="warning" sx={{ mb: 1.5 }}>
                    {sportData.error}
                  </Alert>
                )}

                {(!sportData.matches || sportData.matches.length === 0) ? (
                  <Typography variant="body2" sx={{ color: "text.disabled", fontStyle: "italic" }}>
                    No suggested matches returned.
                  </Typography>
                ) : (
                  <Box sx={{ display: "flex", flexDirection: "column", gap: 1.2 }}>
                    {sportData.matches.map((m, idx) => (
                      <Paper
                        key={idx}
                        elevation={0}
                        sx={{
                          p: 1.8,
                          bgcolor: "rgba(0,0,0,0.25)",
                          border: "1px solid rgba(255,255,255,0.06)",
                          borderRadius: "8px",
                          display: "flex",
                          justifyContent: "space-between",
                          alignItems: "center",
                          gap: 2,
                          "&:hover": { borderColor: "rgba(6, 182, 212, 0.4)" },
                        }}
                      >
                        <Box sx={{ flex: 1, minWidth: 0 }}>
                          <Typography variant="body2" sx={{ fontFamily: "monospace", color: "#E2E8F0", fontSize: "0.82rem" }}>
                            {formatSuggestedMatch(m)}
                          </Typography>
                        </Box>
                        <Box sx={{ display: "flex", gap: 1 }}>
                          <Button
                            variant="contained"
                            color="secondary"
                            size="small"
                            onClick={() => handleUseMatch(m)}
                            disabled={executing}
                            sx={{ fontWeight: 700 }}
                          >
                            Use Match
                          </Button>
                          <Button
                            variant="outlined"
                            color="primary"
                            size="small"
                            onClick={() => handleRunSuggested(m)}
                            disabled={executing}
                            startIcon={<Play size={14} />}
                            sx={{ fontWeight: 700, minWidth: 70 }}
                          >
                            Run
                          </Button>
                        </Box>
                      </Paper>
                    ))}
                  </Box>
                )}
              </Box>
            ))}
          </Box>
        )}
      </Card>

      {/* ========================================================================= */}
      {/* SECTION 2: MANUAL PICK FORM (Exact Streamlit Parity)                      */}
      {/* ========================================================================= */}
      <Card sx={{ p: 3, bgcolor: "background.paper", border: "1px solid rgba(255,255,255,0.08)" }}>
        <Typography variant="h6" sx={{ fontWeight: 700, mb: 2 }}>
          Manual Pick Analysis
        </Typography>

        <Box component="form" onSubmit={handleManualSubmit} sx={{ display: "flex", flexDirection: "column", gap: 2.5 }}>
          <Box sx={{ display: "grid", gridTemplateColumns: { xs: "1fr", md: sport === "NFL" ? "1fr 1fr" : "1fr" }, gap: 2 }}>
            <FormControl fullWidth size="small">
              <InputLabel id="manual-sport-label">Sport</InputLabel>
              <Select
                labelId="manual-sport-label"
                id="manual-sport-select"
                inputProps={{ "data-testid": "manual-sport-input" }}
                value={sport}
                label="Sport"
                onChange={(e) => handleSportChange(e.target.value)}
              >
                <MenuItem value="Soccer">Soccer</MenuItem>
                <MenuItem value="Basketball">Basketball</MenuItem>
                <MenuItem value="Baseball">Baseball</MenuItem>
                <MenuItem value="NFL">NFL</MenuItem>
              </Select>
            </FormControl>

            {sport === "NFL" && (
              <FormControl fullWidth size="small">
                <InputLabel>NFL markets</InputLabel>
                <Select
                  value={nflGroup}
                  label="NFL markets"
                  onChange={(e) => handleNflGroupChange(e.target.value)}
                >
                  <MenuItem value="All">All</MenuItem>
                  <MenuItem value="Player props">Player props</MenuItem>
                  <MenuItem value="Game bets">Game bets</MenuItem>
                </Select>
              </FormControl>
            )}
          </Box>

          <TextField
            type="date"
            label="Match date"
            value={matchDate}
            onChange={(e) => setMatchDate(e.target.value)}
            size="small"
            InputLabelProps={{ shrink: true }}
            fullWidth
          />

          <Box sx={{ display: "grid", gridTemplateColumns: { xs: "1fr", md: "1fr 1fr" }, gap: 2 }}>
            <TextField
              label="Home team"
              value={homeTeam}
              onChange={(e) => setHomeTeam(e.target.value)}
              size="small"
              fullWidth
              helperText={currentHints.home}
            />
            <TextField
              label="Away team"
              value={awayTeam}
              onChange={(e) => setAwayTeam(e.target.value)}
              size="small"
              fullWidth
              helperText={currentHints.away}
            />
          </Box>

          {/* Baseball Specific Markets */}
          {sport.toLowerCase() === "baseball" && (
            <Box sx={{ display: "grid", gridTemplateColumns: { xs: "1fr", md: "1fr 2fr" }, gap: 2 }}>
              <TextField label="League" value="MLB" disabled size="small" fullWidth />
              <FormControl fullWidth size="small">
                <InputLabel id="baseball-markets-label">Markets</InputLabel>
                <Select
                  labelId="baseball-markets-label"
                  id="baseball-markets-select"
                  multiple
                  value={selectedBaseballMarkets}
                  onChange={(e: any) => setSelectedBaseballMarkets(e.target.value)}
                  renderValue={(selected) => selected.join(", ")}
                  label="Markets"
                >
                  {BASEBALL_MARKETS.map((m) => (
                    <MenuItem key={m} value={m}>
                      {m}
                    </MenuItem>
                  ))}
                </Select>
              </FormControl>
            </Box>
          )}

          {/* NFL Specific Markets */}
          {sport === "NFL" && (
            <Box sx={{ display: "flex", flexDirection: "column", gap: 1 }}>
              <FormControl fullWidth size="small">
                <InputLabel id="nfl-markets-label">Markets</InputLabel>
                <Select
                  labelId="nfl-markets-label"
                  id="nfl-markets-select"
                  multiple
                  value={selectedNflMarkets}
                  onChange={(e: any) => setSelectedNflMarkets(e.target.value)}
                  renderValue={(selected) => selected.join(", ")}
                  label="Markets"
                >
                  {(nflGroup === "Player props"
                    ? NFL_PLAYER_MARKETS
                    : nflGroup === "Game bets"
                    ? NFL_GAME_MARKETS
                    : NFL_ALL_MARKETS
                  ).map((m) => (
                    <MenuItem key={m} value={m}>
                      {m}
                    </MenuItem>
                  ))}
                </Select>
              </FormControl>
              <Typography variant="caption" sx={{ color: "text.secondary" }}>
                Full-game pregame only. NFL results are graded manually.
              </Typography>
            </Box>
          )}

          {/* Form Sliders & Flags */}
          <Box sx={{ display: "grid", gridTemplateColumns: { xs: "1fr", sm: "repeat(4, 1fr)" }, gap: 2, alignItems: "center" }}>
            <Box sx={{ px: 1 }}>
              <Typography variant="caption" sx={{ color: "text.secondary" }}>
                Top N picks: <strong>{topN}</strong>
              </Typography>
              <Slider
                value={topN}
                onChange={(_, val) => setTopN(val as number)}
                min={1}
                max={10}
                step={1}
                size="small"
                valueLabelDisplay="auto"
              />
            </Box>

            <FormControlLabel
              control={
                <Checkbox
                  checked={addExplanations}
                  onChange={(e) => setAddExplanations(e.target.checked)}
                  size="small"
                />
              }
              label={<Typography variant="body2">Add pick explanations</Typography>}
            />

            <FormControlLabel
              control={
                <Checkbox
                  checked={allowFallback}
                  onChange={(e) => setAllowFallback(e.target.checked)}
                  size="small"
                />
              }
              label={<Typography variant="body2">Allow fallback</Typography>}
            />

            <FormControlLabel
              control={
                <Checkbox
                  checked={fireAndForget}
                  onChange={(e) => setFireAndForget(e.target.checked)}
                  size="small"
                />
              }
              label={<Typography variant="body2">Fire & forget</Typography>}
            />
          </Box>

          <Button
            type="submit"
            variant="contained"
            color="primary"
            size="large"
            disabled={executing}
            startIcon={executing ? <CircularProgress size={18} color="inherit" /> : <Zap size={18} />}
            sx={{ py: 1.2, fontWeight: 700 }}
          >
            {executing ? "Running Pipeline..." : "Generate"}
          </Button>
        </Box>
      </Card>

      {/* ========================================================================= */}
      {/* SECTION 3: PIPELINE EXECUTION BANNER & NOTICES                            */}
      {/* ========================================================================= */}
      {executing && (
        <Card sx={{ p: 3, bgcolor: "background.paper", border: "1px solid rgba(6, 182, 212, 0.3)" }}>
          <Box sx={{ display: "flex", alignItems: "center", gap: 2, mb: 1.5 }}>
            <CircularProgress size={24} color="primary" />
            <Typography variant="subtitle1" sx={{ fontWeight: 700 }}>
              {statusMessage}
            </Typography>
          </Box>
          <LinearProgress sx={{ height: 6, borderRadius: 3 }} />
        </Card>
      )}

      {pipelineError && (
        <Alert severity="error" sx={{ fontWeight: 600 }}>
          {pipelineError}
        </Alert>
      )}

      {fireAndForgetSuccess && (
        <Alert
          severity="success"
          data-testid="fire-and-forget-alert"
          action={
            <Box sx={{ display: "flex", gap: 1 }}>
              {fireAndForgetSuccess.operationId && onNavigateToDiagnostics && (
                <Button
                  color="inherit"
                  size="small"
                  onClick={() => onNavigateToDiagnostics(fireAndForgetSuccess.operationId!)}
                  startIcon={<Activity size={14} />}
                  sx={{ fontWeight: 700 }}
                >
                  View Diagnostics
                </Button>
              )}
              <Button
                color="inherit"
                size="small"
                onClick={() => setFireAndForgetSuccess(null)}
              >
                Dismiss
              </Button>
            </Box>
          }
        >
          Pick <strong>{fireAndForgetSuccess.pickId}</strong> submitted. Pipeline is running in the background — check <strong>Pick History</strong> when ready.
        </Alert>
      )}

      {/* ========================================================================= */}
      {/* SECTION 4: PICK REPORT & EXPANDERS                                        */}
      {/* ========================================================================= */}
      {pickResult && (
        <Box sx={{ display: "flex", flexDirection: "column", gap: 3 }}>
          {/* Status & Diagnostic Banner */}
          <Paper
            elevation={0}
            sx={{
              p: 2,
              bgcolor: "rgba(0,0,0,0.3)",
              border: "1px solid rgba(255,255,255,0.08)",
              borderRadius: "8px",
              display: "flex",
              justifyContent: "space-between",
              alignItems: "center",
              flexWrap: "wrap",
              gap: 1.5,
            }}
          >
            <Box>
              <Typography variant="subtitle1" sx={{ fontWeight: 800 }}>
                Pick ID: <span style={{ fontFamily: "monospace", color: "#06B6D4" }}>{pickResult.id}</span>
              </Typography>
              <Typography variant="caption" sx={{ color: "text.secondary" }}>
                Created: {pickResult.created_at} · Latency: {pickResult.latency_ms ?? "—"} ms · Status: {pickResult.status}
              </Typography>
              <Typography variant="caption" sx={{ color: "text.secondary", display: "block" }}>
                Result: <strong>{runState(pickResult).label}</strong>
              </Typography>
            </Box>

            {pickResult.operation_id && (
              <Button
                variant="outlined"
                size="small"
                startIcon={<Activity size={14} />}
                onClick={() => {
                  if (onNavigateToDiagnostics && pickResult.operation_id) {
                    onNavigateToDiagnostics(pickResult.operation_id);
                  } else {
                    window.location.hash = "diagnostics";
                  }
                }}
                sx={{ fontWeight: 600 }}
              >
                View Diagnostics
              </Button>
            )}
          </Paper>

          {/* Outcome Alerts */}
          {pickResult.sport === "nfl" && pickNflRecommendationSummary(pickResult) && (
            <Alert severity={pickResult.outcome === "no_picks" ? "info" : "warning"}>{pickNflRecommendationSummary(pickResult)!.message}</Alert>
          )}
          {pickResult.outcome === "no_picks" && (
            <Alert severity="info">
              Analysis completed, but no verified picks qualified. View diagnostics for the recorded reasons.
            </Alert>
          )}

          {pickResult.outcome === "partial" && (
            <Alert severity="warning">
              Partial results saved as id <code>{pickResult.id}</code>. View diagnostics for the incomplete stages.
            </Alert>
          )}

          {/* Full Markdown Report */}
          {pickResult.report_markdown && (
            <Card sx={{ p: 3.5, bgcolor: "background.paper", border: "1px solid rgba(255,255,255,0.08)" }}>
              <MarkdownRenderer content={pickResult.report_markdown} />
            </Card>
          )}

          {/* Expanders for Raw Scores, Trace, Match Inputs */}
          <Box sx={{ display: "flex", flexDirection: "column", gap: 1 }}>
            <Accordion sx={{ bgcolor: "background.paper", border: "1px solid rgba(255,255,255,0.08)" }}>
              <AccordionSummary expandIcon={<ChevronDown size={18} color="#94A3B8" />}>
                <Typography variant="subtitle2" sx={{ fontWeight: 700 }}>
                  Raw scores ({pickResult.scores?.length || 0})
                </Typography>
              </AccordionSummary>
              <AccordionDetails>
                <Box sx={{ bgcolor: "#070B14", p: 2, borderRadius: "6px", overflowX: "auto" }}>
                  <pre style={{ margin: 0, fontFamily: "monospace", fontSize: "0.8rem", color: "#E2E8F0" }}>
                    {JSON.stringify(pickResult.scores || [], null, 2)}
                  </pre>
                </Box>
              </AccordionDetails>
            </Accordion>

            {pickResult.trace && (
              <Accordion sx={{ bgcolor: "background.paper", border: "1px solid rgba(255,255,255,0.08)" }}>
                <AccordionSummary expandIcon={<ChevronDown size={18} color="#94A3B8" />}>
                  <Typography variant="subtitle2" sx={{ fontWeight: 700 }}>
                    Pipeline Trace
                  </Typography>
                </AccordionSummary>
                <AccordionDetails>
                  <Box sx={{ bgcolor: "#070B14", p: 2, borderRadius: "6px", overflowX: "auto" }}>
                    <pre style={{ margin: 0, fontFamily: "monospace", fontSize: "0.8rem", color: "#E2E8F0" }}>
                      {JSON.stringify(pickResult.trace, null, 2)}
                    </pre>
                  </Box>
                </AccordionDetails>
              </Accordion>
            )}

            {pickResult.match_inputs && (
              <Accordion sx={{ bgcolor: "background.paper", border: "1px solid rgba(255,255,255,0.08)" }}>
                <AccordionSummary expandIcon={<ChevronDown size={18} color="#94A3B8" />}>
                  <Typography variant="subtitle2" sx={{ fontWeight: 700 }}>
                    Match Inputs
                  </Typography>
                </AccordionSummary>
                <AccordionDetails>
                  <Box sx={{ bgcolor: "#070B14", p: 2, borderRadius: "6px", overflowX: "auto" }}>
                    <pre style={{ margin: 0, fontFamily: "monospace", fontSize: "0.8rem", color: "#E2E8F0" }}>
                      {JSON.stringify(pickResult.match_inputs, null, 2)}
                    </pre>
                  </Box>
                </AccordionDetails>
              </Accordion>
            )}
          </Box>

          {/* ========================================================================= */}
          {/* SECTION 5: PRIZEPICKS AVAILABILITY CHECK (Streamlit Lines 318–378)       */}
          {/* ========================================================================= */}
          {pickResult.outcome !== "no_picks" && (
            <Card sx={{ p: 3, bgcolor: "background.paper", border: "1px solid rgba(255,255,255,0.08)" }}>
              <Box sx={{ display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: 2, mb: 2 }}>
                <Box>
                  <Typography variant="h6" sx={{ fontWeight: 700 }}>
                    Availability Check
                  </Typography>
                  <Typography variant="caption" sx={{ color: "text.secondary" }}>
                    Live sportsbook board confirmation across verified platforms.
                  </Typography>
                </Box>

                <Box sx={{ display: "flex", alignItems: "center", gap: 1.5 }}>
                  <FormControl size="small" sx={{ minWidth: 150 }}>
                    <InputLabel>Platforms</InputLabel>
                    <Select
                      multiple
                      value={availPlatforms}
                      onChange={(e: any) => setAvailPlatforms(e.target.value)}
                      renderValue={(sel) => sel.join(", ")}
                      label="Platforms"
                    >
                      <MenuItem value="prizepicks">prizepicks</MenuItem>
                    </Select>
                  </FormControl>

                  <Button
                    variant="outlined"
                    color="primary"
                    size="small"
                    onClick={() => fetchAvailability(pickResult.id, availPlatforms)}
                    disabled={checkingAvail}
                    startIcon={checkingAvail ? <CircularProgress size={14} color="inherit" /> : <Zap size={14} />}
                    sx={{ fontWeight: 700 }}
                  >
                    Refresh Availability
                  </Button>
                </Box>
              </Box>

              {availFallbackNotice && (
                <Alert severity="info" sx={{ mb: 2 }}>
                  {availFallbackNotice}
                </Alert>
              )}

              {availBadges.length === 0 && !checkingAvail && !availFallbackNotice && (
                <Typography variant="body2" sx={{ color: "text.secondary", fontStyle: "italic" }}>
                  No availability data returned for this pick.
                </Typography>
              )}

              {availBadges.length > 0 && (
                <Box sx={{ display: "flex", flexDirection: "column", gap: 1.5 }}>
                  {availBadges.map((badge, idx) => {
                    const isAvail = badge.status === "available";
                    const isDiff =
                      badge.status === "available" &&
                      badge.platform_line != null &&
                      Math.abs(badge.platform_line - badge.line) > 0.01;
                    const isUnavail = badge.status === "unavailable";

                    let severity: "success" | "warning" | "error" | "info" = "info";
                    let icon = <HelpCircle size={18} color="#94A3B8" />;
                    let statusText = `Could not check ${badge.platform}`;
                    let badgeLabel = "Unknown";

                    if (isDiff) {
                      severity = "warning";
                      icon = <AlertTriangle size={18} color="#F59E0B" />;
                      statusText = `Line differs: ${badge.platform_line} vs recommended ${badge.line}`;
                      badgeLabel = "Line Differs";
                    } else if (isAvail) {
                      severity = "success";
                      icon = <CheckCircle2 size={18} color="#10B981" />;
                      statusText = `Available on ${badge.platform}`;
                      badgeLabel = "Available";
                    } else if (isUnavail) {
                      severity = "error";
                      icon = <XCircle size={18} color="#EF4444" />;
                      statusText = `Not available on ${badge.platform}`;
                      badgeLabel = "Not Available";
                    }

                    return (
                      <Paper
                        key={idx}
                        elevation={0}
                        sx={{
                          p: 1.5,
                          bgcolor: "rgba(0,0,0,0.25)",
                          border: "1px solid",
                          borderColor:
                            severity === "success"
                              ? "rgba(16, 185, 129, 0.3)"
                              : severity === "warning"
                              ? "rgba(245, 158, 11, 0.3)"
                              : severity === "error"
                              ? "rgba(239, 68, 68, 0.3)"
                              : "rgba(255,255,255,0.06)",
                          borderRadius: "8px",
                          display: "flex",
                          justifyContent: "space-between",
                          alignItems: "center",
                          gap: 1.5,
                        }}
                      >
                        <Box sx={{ display: "flex", alignItems: "center", gap: 1.5 }}>
                          {icon}
                          <Chip
                            label={badgeLabel}
                            size="small"
                            color={severity === "info" ? "default" : severity}
                            sx={{ fontWeight: 700, fontSize: "0.68rem" }}
                          />
                          <Typography variant="body2" sx={{ fontWeight: 600 }}>
                            <strong>{badge.player}</strong> ({badge.market}) — {statusText}
                          </Typography>
                        </Box>

                        {isAvail && badge.url && (
                          <Button
                            component="a"
                            href={badge.url}
                            target="_blank"
                            rel="noreferrer"
                            size="small"
                            endIcon={<ExternalLink size={14} />}
                            sx={{ fontWeight: 600 }}
                          >
                            Open
                          </Button>
                        )}
                      </Paper>
                    );
                  })}
                </Box>
              )}
            </Card>
          )}
        </Box>
      )}
    </Box>
  );
};
