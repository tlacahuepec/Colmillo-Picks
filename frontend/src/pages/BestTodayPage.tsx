import React, { useState, useEffect, useRef } from "react";
import {
  Box,
  Card,
  Typography,
  Button,
  Select,
  MenuItem,
  FormControl,
  InputLabel,
  Slider,
  CircularProgress,
  LinearProgress,
  Alert,
  Accordion,
  AccordionSummary,
  AccordionDetails,
  Divider,
  Chip,
  Paper,
  TextField,
} from "@mui/material";
import {
  ChevronDown,
  Sparkles,
  Zap,
  RotateCcw,
  Activity,
} from "lucide-react";
import { api } from "../api/client";
import {
  AvailabilityBadge,
  CreateSlatePayload,
  SlateDetail,
  SlateRankedCandidate,
  SlateSummary,
} from "../api/types";
import { SlateCandidateCard } from "../components/Slate/SlateCandidateCard";
import { DEFAULT_TIMEZONE, isRecord, loadPageDraft, localDay, savePageDraft } from "../state/pageDrafts";
import { runState } from "../state/runStatus";

function formatKickoffLocal(kickoffUtc?: string | null): string {
  if (!kickoffUtc) return "—";
  try {
    const dt = new Date(kickoffUtc);
    return dt.toLocaleString(undefined, {
      month: "short",
      day: "numeric",
      hour: "numeric",
      minute: "2-digit",
      hour12: true,
    });
  } catch {
    return kickoffUtc;
  }
}

function confidenceColor(conf: string | number): "success" | "warning" | "error" | "default" {
  const c = String(conf).toLowerCase();
  if (c === "high") return "success";
  if (c === "medium") return "warning";
  if (c === "low") return "error";
  return "default";
}

function buildAvailabilityBatchPayload(candidates: SlateRankedCandidate[]) {
  const payload: any[] = [];
  for (const c of candidates) {
    if (c.subject_type && c.subject_type !== "player") continue;
    if (c.sport === "nfl" && c.line == null) continue;
    const player = c.subject_name || c.player;
    const market = c.market;
    if (!player || !market) continue;
    payload.push({
      ...(c.sport === "nfl" ? { sport: "nfl" } : {}),
      player,
      market,
      line: c.line ?? 0.0,
    });
  }
  return payload;
}

interface BestTodayPageProps {
  onNavigateToDiagnostics?: (operationId: string) => void;
}

type SlateDraft = { savedOn: string; slateDate: string; slateSports: string[]; nflGroup: "all" | "player_props" | "game_bets"; maxMatches: number; topN: number; selectedSlateId: string | null };
const newSlateDraft = (): SlateDraft => ({ savedOn: localDay(), slateDate: localDay(), slateSports: ["Soccer", "Basketball", "Baseball", "NFL"], nflGroup: "all", maxMatches: 3, topN: 10, selectedSlateId: null });
const isSlateDraft = (value: unknown): value is SlateDraft => isRecord(value) && typeof value.savedOn === "string" && typeof value.slateDate === "string" && Array.isArray(value.slateSports) && (value.nflGroup === "all" || value.nflGroup === "player_props" || value.nflGroup === "game_bets");

export const BestTodayPage: React.FC<BestTodayPageProps> = ({ onNavigateToDiagnostics }) => {
  const [initialDraft] = useState(() => {
    const draft = loadPageDraft("slate", newSlateDraft(), isSlateDraft);
    return draft.savedOn === localDay() ? draft : newSlateDraft();
  });
  // ---- Generator Form State ----
  const [slateDate, setSlateDate] = useState<string>(initialDraft.slateDate);
  const [slateSports, setSlateSports] = useState<string[]>(initialDraft.slateSports);
  const [nflGroup, setNflGroup] = useState<"all" | "player_props" | "game_bets">(initialDraft.nflGroup);
  const [maxMatches, setMaxMatches] = useState<number>(initialDraft.maxMatches);
  const [topN, setTopN] = useState<number>(initialDraft.topN);

  // ---- Slate Execution State ----
  const [submitting, setSubmitting] = useState<boolean>(false);
  const [isPolling, setIsPolling] = useState<boolean>(false);
  const [submitMessage, setSubmitMessage] = useState<string>("");
  const [pollError, setPollError] = useState<string | null>(null);
  const [resuming, setResuming] = useState(false);
  const [selectedSlateId, setSelectedSlateId] = useState<string | null>(initialDraft.selectedSlateId);
  const pollIntervalRef = useRef<any>(null);
  const selectedSlateRef = useRef<string | null>(initialDraft.selectedSlateId);
  const detailRequestRef = useRef(0);

  // ---- Recent Slates State ----
  const [slates, setSlates] = useState<SlateSummary[]>([]);
  const [loadingSlates, setLoadingSlates] = useState<boolean>(false);
  const [slatesError, setSlatesError] = useState<string | null>(null);

  // ---- Selected Slate Detail State ----
  const [loadingDetail, setLoadingDetail] = useState<boolean>(false);
  const [slateDetail, setSlateDetail] = useState<SlateDetail | null>(null);
  const [detailError, setDetailError] = useState<string | null>(null);

  // ---- Batch Availability State ----
  const [availBadges, setAvailBadges] = useState<Record<string, AvailabilityBadge>>({});
  const [checkingAvail, setCheckingAvail] = useState<boolean>(false);
  const [availError, setAvailError] = useState<string | null>(null);

  useEffect(() => {
    savePageDraft("slate", { savedOn: localDay(), slateDate, slateSports, nflGroup, maxMatches, topN, selectedSlateId });
  }, [slateDate, slateSports, nflGroup, maxMatches, topN, selectedSlateId]);

  useEffect(() => {
    loadRecentSlates();
    return () => {
      if (pollIntervalRef.current) {
        clearInterval(pollIntervalRef.current);
      }
    };
  }, []);

  const loadRecentSlates = async (preferredSlateId?: string, selectSlate = true) => {
    setLoadingSlates(true);
    setSlatesError(null);
    try {
      const resp = await api.listSlates(10);
      const items = resp.items || [];
      setSlates(items);

      const targetId = preferredSlateId || selectedSlateRef.current;
      const restoredSlate = targetId && items.find((item) => item.id === targetId);
      if (selectSlate && restoredSlate) void handleSelectSlate(restoredSlate.id);
      else if (selectSlate && items.length > 0 && !targetId) void handleSelectSlate(items[0].id);
    } catch (err: any) {
      setSlatesError(err.message || "Failed to load recent slates");
    } finally {
      setLoadingSlates(false);
    }
  };

  const handleSelectSlate = async (slateId: string) => {
    const requestId = detailRequestRef.current + 1;
    detailRequestRef.current = requestId;
    selectedSlateRef.current = slateId;
    if (pollIntervalRef.current) {
      clearInterval(pollIntervalRef.current);
      pollIntervalRef.current = null;
    }
    setSelectedSlateId(slateId);
    setLoadingDetail(true);
    setDetailError(null);
    setPollError(null);
    setAvailBadges({});
    setAvailError(null);

    try {
      const detail = await api.getSlate(slateId);
      if (detailRequestRef.current !== requestId) return;
      setSlateDetail(detail);

      // If still pending/running, start polling status
      if (detail.status === "pending" || detail.status === "queued" || detail.status === "running") {
        pollSlateStatus(slateId);
      } else {
        setIsPolling(false);
      }
    } catch (err: any) {
      if (detailRequestRef.current !== requestId) return;
      setDetailError(err.message || "Failed to fetch slate details");
    } finally {
      if (detailRequestRef.current === requestId) setLoadingDetail(false);
    }
  };

  const pollSlateStatus = (slateId: string) => {
    if (pollIntervalRef.current) {
      clearInterval(pollIntervalRef.current);
      pollIntervalRef.current = null;
    }
    setIsPolling(true);
    setPollError(null);
    let inFlight = false;

    const check = async () => {
      if (inFlight || selectedSlateRef.current !== slateId) return;
      inFlight = true;
      try {
        const stat = await api.getSlateStatus(slateId);
        if (selectedSlateRef.current !== slateId) return;
        if (stat.status === "success" || stat.status === "partial" || stat.status === "failed" || stat.status === "interrupted") {
          if (pollIntervalRef.current) {
            clearInterval(pollIntervalRef.current);
            pollIntervalRef.current = null;
          }
          setIsPolling(false);
          const finishedDetail = await api.getSlate(slateId);
          if (selectedSlateRef.current !== slateId) return;
          setSlateDetail(finishedDetail);
          loadRecentSlates();
        }
      } catch {
        if (selectedSlateRef.current !== slateId) return;
        if (pollIntervalRef.current) {
          clearInterval(pollIntervalRef.current);
          pollIntervalRef.current = null;
        }
        setIsPolling(false);
        setPollError(`Lost connection while observing slate ${slateId}. The pipeline may still be running.`);
      } finally {
        inFlight = false;
      }
    };

    check();
    pollIntervalRef.current = setInterval(check, 2000);
  };

  const handleGenerateSlate = async (e: React.FormEvent) => {
    e.preventDefault();
    setSubmitting(true);
    setSubmitMessage("Submitting slate job to pipeline...");

    const normalizedSports = slateSports.map((s) => s.toLowerCase());
    const payload: CreateSlatePayload = {
      date: slateDate,
      sports: normalizedSports,
      max_matches_per_sport: maxMatches,
      top_n: topN,
      nfl_market_group: nflGroup,
      timezone: DEFAULT_TIMEZONE,
    };

    try {
      const accepted = await api.createSlate(payload);
      const sid = accepted.id;
      selectedSlateRef.current = sid;
      setSelectedSlateId(sid);
      setSubmitMessage(`Slate ${sid} submitted! Polling pipeline...`);

      // Select the accepted resource before refreshing the rail so a stale list
      // cannot briefly re-select the previous slate.
      await handleSelectSlate(sid);
      void loadRecentSlates(sid, false);
    } catch (err: any) {
      setDetailError(err.message || "Failed to submit slate request");
    } finally {
      setSubmitting(false);
    }
  };

  const handleCheckAvailability = async () => {
    if (!slateDetail || !slateDetail.candidates) return;
    setCheckingAvail(true);
    setAvailError(null);

    const candidatesPayload = buildAvailabilityBatchPayload(slateDetail.candidates);
    if (candidatesPayload.length === 0) {
      setCheckingAvail(false);
      return;
    }

    try {
      const resp = await api.checkAvailabilityBatch(candidatesPayload);
      const map: Record<string, AvailabilityBadge> = {};
      (resp.badges || []).forEach((b) => {
        const key = `${b.player.toLowerCase()}-${b.market.toLowerCase()}`;
        map[key] = b;
      });
      setAvailBadges(map);
    } catch (err: any) {
      setAvailError(err.message || "Batch availability check failed");
    } finally {
      setCheckingAvail(false);
    }
  };

  const retrySelectedSlate = () => {
    if (selectedSlateId) void handleSelectSlate(selectedSlateId);
  };

  const resumeSelectedSlate = async () => {
    if (!selectedSlateId) return;
    setResuming(true);
    setPollError(null);
    try {
      await api.resumeSlate(selectedSlateId);
      await handleSelectSlate(selectedSlateId);
    } catch (err: any) {
      setPollError(err?.message || "Unable to resume this slate.");
    } finally {
      setResuming(false);
    }
  };

  return (
    <Box sx={{ display: "flex", flexDirection: "column", gap: 3.5, pb: 6 }}>
      {/* Header */}
      <Box>
        <Typography variant="h4" sx={{ fontWeight: 800, letterSpacing: "-0.02em", color: "#FFF" }}>
          Best Today Slate
        </Typography>
        <Typography variant="body2" sx={{ color: "text.secondary", mt: 0.5 }}>
          Generate a ranked cross-sport slate of player props and NFL game bets across today's sports calendar.
        </Typography>
      </Box>

      {/* ========================================================================= */}
      {/* SECTION 1: SLATE GENERATOR FORM                                           */}
      {/* ========================================================================= */}
      <Card sx={{ p: 3, bgcolor: "background.paper", border: "1px solid rgba(255,255,255,0.08)" }}>
        <Typography variant="h6" sx={{ fontWeight: 700, mb: 2, display: "flex", alignItems: "center", gap: 1 }}>
          <Sparkles size={18} color="#06B6D4" />
          Cross-Sport Slate Generator
        </Typography>

        <Box component="form" onSubmit={handleGenerateSlate} sx={{ display: "flex", flexDirection: "column", gap: 2.5 }}>
          <Box sx={{ display: "grid", gridTemplateColumns: { xs: "1fr", md: "1.2fr 2fr 1.2fr" }, gap: 2 }}>
            <TextField
              type="date"
              label="Date"
              value={slateDate}
              onChange={(e) => setSlateDate(e.target.value)}
              size="small"
              InputLabelProps={{ shrink: true }}
              fullWidth
            />

            <FormControl fullWidth size="small">
              <InputLabel>Sports</InputLabel>
              <Select
                multiple
                value={slateSports}
                onChange={(e: any) => setSlateSports(e.target.value)}
                renderValue={(selected) => selected.join(", ")}
                label="Sports"
              >
                {["Soccer", "Basketball", "Baseball", "NFL"].map((s) => (
                  <MenuItem key={s} value={s}>
                    {s}
                  </MenuItem>
                ))}
              </Select>
            </FormControl>

            <FormControl fullWidth size="small">
              <InputLabel>NFL markets</InputLabel>
              <Select
                value={nflGroup}
                label="NFL markets"
                onChange={(e: any) => setNflGroup(e.target.value)}
              >
                <MenuItem value="all">All</MenuItem>
                <MenuItem value="player_props">Player props</MenuItem>
                <MenuItem value="game_bets">Game bets</MenuItem>
              </Select>
            </FormControl>
          </Box>

          <Box sx={{ display: "grid", gridTemplateColumns: { xs: "1fr", md: "1fr 1fr" }, gap: 3 }}>
            <Box sx={{ px: 1 }}>
              <Typography variant="caption" sx={{ color: "text.secondary" }}>
                Max matches per sport: <strong>{maxMatches}</strong>
              </Typography>
              <Slider
                value={maxMatches}
                onChange={(_, val) => setMaxMatches(val as number)}
                min={1}
                max={5}
                step={1}
                size="small"
                valueLabelDisplay="auto"
              />
            </Box>

            <Box sx={{ px: 1 }}>
              <Typography variant="caption" sx={{ color: "text.secondary" }}>
                Top N candidates: <strong>{topN}</strong>
              </Typography>
              <Slider
                value={topN}
                onChange={(_, val) => setTopN(val as number)}
                min={1}
                max={20}
                step={1}
                size="small"
                valueLabelDisplay="auto"
              />
            </Box>
          </Box>

          <Button
            type="submit"
            variant="contained"
            color="primary"
            size="large"
            disabled={submitting || isPolling}
            startIcon={submitting || isPolling ? <CircularProgress size={18} color="inherit" /> : <Zap size={18} />}
            sx={{ alignSelf: "flex-start", px: 4, py: 1.2, fontWeight: 700 }}
          >
            {submitting || isPolling ? "Generating Slate..." : "Generate Best Today"}
          </Button>
        </Box>
      </Card>

      {/* PIPELINE EXECUTION BANNER */}
      {(submitting || isPolling) && (
        <Card sx={{ p: 3, bgcolor: "background.paper", border: "1px solid rgba(6, 182, 212, 0.3)" }}>
          <Box sx={{ display: "flex", alignItems: "center", gap: 2, mb: 1.5 }}>
            <CircularProgress size={24} color="primary" />
            <Typography variant="subtitle1" sx={{ fontWeight: 700 }}>
              {submitMessage || "Processing cross-sport slate pipeline..."}
            </Typography>
          </Box>
          <LinearProgress sx={{ height: 6, borderRadius: 3 }} />
        </Card>
      )}

      {pollError && (
        <Alert severity="warning" action={<Button color="inherit" size="small" onClick={retrySelectedSlate}>Resume observation</Button>}>
          {pollError}
        </Alert>
      )}

      {/* ========================================================================= */}
      {/* SECTION 2: RECENT SLATES & SELECTED SLATE DETAIL                          */}
      {/* ========================================================================= */}
      <Box sx={{ display: "grid", gridTemplateColumns: { xs: "1fr", lg: "340px 1fr" }, gap: 3, alignItems: "start" }}>
        {/* Left: Recent Slates Rail */}
        <Card sx={{ bgcolor: "background.paper", border: "1px solid rgba(255,255,255,0.08)", overflow: "hidden" }}>
          <Box sx={{ p: 2, borderBottom: "1px solid rgba(255,255,255,0.08)", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
            <Typography variant="subtitle2" sx={{ fontWeight: 700 }}>
              Recent Slates
            </Typography>
            <Button size="small" onClick={() => void loadRecentSlates()} startIcon={<RotateCcw size={14} />}>
              Refresh
            </Button>
          </Box>

          {loadingSlates ? (
            <Box sx={{ p: 4, textAlign: "center" }}>
              <CircularProgress size={24} />
            </Box>
          ) : slatesError ? (
            <Box sx={{ p: 2 }}>
              <Alert severity="error" action={<Button color="inherit" size="small" onClick={() => void loadRecentSlates()}>Retry</Button>}>{slatesError}</Alert>
            </Box>
          ) : slates.length === 0 ? (
            <Box sx={{ p: 3, textAlign: "center" }}>
              <Typography variant="body2" sx={{ color: "text.secondary" }}>
                No slates yet. Submit one above!
              </Typography>
            </Box>
          ) : (
            <Box sx={{ maxHeight: 600, overflowY: "auto", display: "flex", flexDirection: "column" }}>
              {slates.map((s) => {
                const isSelected = s.id === selectedSlateId;
                const req = s.request || {};
                const sportsStr = req.sports && req.sports.length > 0 ? req.sports.join(", ") : "all";
                const state = runState(s);
                return (
                  <Box
                    key={s.id}
                    onClick={() => handleSelectSlate(s.id)}
                    sx={{
                      p: 1.8,
                      borderBottom: "1px solid rgba(255,255,255,0.05)",
                      cursor: "pointer",
                      bgcolor: isSelected ? "rgba(6, 182, 212, 0.12)" : "transparent",
                      borderLeft: isSelected ? "3px solid #06B6D4" : "3px solid transparent",
                      "&:hover": { bgcolor: isSelected ? "rgba(6, 182, 212, 0.16)" : "rgba(255,255,255,0.03)" },
                    }}
                  >
                    <Typography variant="caption" sx={{ color: "text.secondary", fontFamily: "monospace", display: "block" }}>
                      <span>{s.id}</span> · {req.date || s.created_at?.split("T")[0] || "—"}
                    </Typography>
                    <Typography variant="body2" sx={{ fontWeight: 700, color: isSelected ? "#06B6D4" : "#FFF", mt: 0.3 }}>
                      {sportsStr}
                    </Typography>
                    <Box sx={{ display: "flex", alignItems: "center", gap: 1, mt: 0.8 }}>
                      <Chip
                        label={state.label}
                        size="small"
                        color={state.color}
                        sx={{ fontSize: "0.68rem", height: 20 }}
                      />
                      {s.latency_ms != null && (
                        <Typography variant="caption" sx={{ color: "text.secondary" }}>
                          {s.latency_ms}ms
                        </Typography>
                      )}
                    </Box>
                  </Box>
                );
              })}
            </Box>
          )}
        </Card>

        {/* Right: Selected Slate Results */}
        <Box>
          {loadingDetail ? (
            <Card sx={{ p: 6, textAlign: "center", bgcolor: "background.paper" }}>
              <CircularProgress size={32} />
              <Typography variant="body2" sx={{ color: "text.secondary", mt: 2 }}>
                Loading slate details...
              </Typography>
            </Card>
          ) : detailError ? (
            <Alert severity="error" action={selectedSlateId ? <Button color="inherit" size="small" onClick={retrySelectedSlate}>Retry</Button> : undefined}>{detailError}</Alert>
          ) : !slateDetail ? (
            <Card sx={{ p: 6, textAlign: "center", bgcolor: "background.paper", borderStyle: "dashed" }}>
              <Sparkles size={40} color="#64748B" style={{ marginBottom: 12 }} />
              <Typography variant="h6" sx={{ color: "text.secondary" }}>
                Select or generate a slate to view top candidate props
              </Typography>
            </Card>
          ) : (
            <Box sx={{ display: "flex", flexDirection: "column", gap: 3 }}>
              {/* Slate Status Banner */}
              <Paper
                elevation={0}
                sx={{
                  p: 2.5,
                  bgcolor: "background.paper",
                  border: "1px solid rgba(255,255,255,0.08)",
                  borderRadius: "8px",
                  display: "flex",
                  justifyContent: "space-between",
                  alignItems: "center",
                  flexWrap: "wrap",
                  gap: 2,
                }}
              >
                <Box>
                  <Typography variant="h6" sx={{ fontWeight: 800, color: "#FFF" }}>
                    Slate ID: <span style={{ fontFamily: "monospace", color: "#06B6D4" }}>{slateDetail.id}</span>
                  </Typography>
                  <Typography variant="caption" sx={{ color: "text.secondary" }}>
                    Status: <strong>{slateDetail.status}</strong> · Completed: {slateDetail.matches_completed ?? slateDetail.matches_attempted ?? 0} / {slateDetail.matches_discovered ?? "?"}
                  </Typography>
                  <Typography variant="caption" sx={{ color: "text.secondary", display: "block" }}>
                    Result: <strong>{runState(slateDetail).label}</strong>
                  </Typography>
                </Box>

                {slateDetail.operation_id && (
                  <Button
                    variant="outlined"
                    size="small"
                    startIcon={<Activity size={14} />}
                    onClick={() => {
                      if (onNavigateToDiagnostics && slateDetail.operation_id) {
                        onNavigateToDiagnostics(slateDetail.operation_id);
                      } else {
                        window.location.hash = "diagnostics";
                      }
                    }}
                  >
                    View Diagnostics
                  </Button>
                )}
              </Paper>

                {slateDetail.status === "failed" && (
                  <Alert severity="error">
                    Slate failed at stage <strong>{slateDetail.error_stage || "unknown"}</strong>: {slateDetail.error_message || "Unknown error"}
                  </Alert>
                )}

                {slateDetail.status === "interrupted" && (
                  <Alert severity="warning" action={<Button color="inherit" size="small" disabled={resuming} onClick={() => void resumeSelectedSlate()}>{resuming ? "Resuming…" : "Resume"}</Button>}>
                    {slateDetail.stop_reason === "budget_exhausted"
                      ? "The slate reached its execution budget. Completed results are preserved; resume to run remaining matches."
                      : "Slate execution was interrupted. Completed results are preserved; resume to run remaining matches."}
                  </Alert>
                )}

              {/* Partial Pipeline Summary Alert */}
              {(() => {
                const pendingRuns = (slateDetail.match_runs || []).filter((r) => r.status === "pending_data");
                const failedRuns = (slateDetail.match_runs || []).filter((r) => r.status === "failed");
                const hasPartialIssues = slateDetail.status === "partial" || pendingRuns.length > 0 || failedRuns.length > 0;
                if (!hasPartialIssues) return null;

                return (
                  <Alert severity="warning" sx={{ mb: 1 }}>
                    <Typography variant="subtitle2" sx={{ fontWeight: 700, mb: 0.5 }}>
                      Partial Pipeline Results
                    </Typography>
                    <Typography variant="body2" sx={{ mb: 1 }}>
                      Some scheduled matches encountered errors or are waiting for confirmed lineups:
                    </Typography>
                    <Box component="ul" sx={{ m: 0, pl: 2.5 }}>
                      {pendingRuns.map((r, i) => (
                        <li key={`pending-${i}`}>
                          <strong>[{r.sport.toUpperCase()}] {r.home_team} vs {r.away_team}</strong>: waiting for lineup — {r.error_message || "lineup pending"}
                        </li>
                      ))}
                      {failedRuns.map((r, i) => (
                        <li key={`failed-${i}`}>
                          <strong>[{r.sport.toUpperCase()}] {r.home_team} vs {r.away_team}</strong>: failed — {r.error_message || "unknown error"}
                        </li>
                      ))}
                    </Box>
                  </Alert>
                );
              })()}

              {/* Timing & Metadata Expander */}
              <Accordion sx={{ bgcolor: "background.paper", border: "1px solid rgba(255,255,255,0.08)" }}>
                <AccordionSummary expandIcon={<ChevronDown size={18} color="#94A3B8" />}>
                  <Typography variant="subtitle2" sx={{ fontWeight: 700 }}>
                    Timing & Metadata
                  </Typography>
                </AccordionSummary>
                <AccordionDetails>
                  <Box sx={{ display: "grid", gridTemplateColumns: { xs: "1fr", sm: "repeat(3, 1fr)" }, gap: 2, mb: 2 }}>
                    <Box sx={{ p: 1.5, bgcolor: "rgba(0,0,0,0.2)", borderRadius: "6px", textAlign: "center" }}>
                      <Typography variant="caption" sx={{ color: "text.secondary" }}>Total Latency</Typography>
                      <Typography variant="h6" sx={{ fontWeight: 700 }}>{slateDetail.latency_ms ?? "—"} ms</Typography>
                    </Box>
                    <Box sx={{ p: 1.5, bgcolor: "rgba(0,0,0,0.2)", borderRadius: "6px", textAlign: "center" }}>
                      <Typography variant="caption" sx={{ color: "text.secondary" }}>Discovery Latency</Typography>
                      <Typography variant="h6" sx={{ fontWeight: 700 }}>{slateDetail.discovery_latency_ms ?? "—"} ms</Typography>
                    </Box>
                    <Box sx={{ p: 1.5, bgcolor: "rgba(0,0,0,0.2)", borderRadius: "6px", textAlign: "center" }}>
                      <Typography variant="caption" sx={{ color: "text.secondary" }}>Matches</Typography>
                      <Typography variant="h6" sx={{ fontWeight: 700 }}>{slateDetail.matches_succeeded} / {slateDetail.matches_attempted}</Typography>
                    </Box>
                  </Box>

                  {slateDetail.total_tokens != null && (
                    <Typography variant="caption" sx={{ color: "text.secondary", fontFamily: "monospace" }}>
                      Tokens: {slateDetail.prompt_tokens?.toLocaleString()} prompt + {slateDetail.completion_tokens?.toLocaleString()} completion = {slateDetail.total_tokens.toLocaleString()} total
                    </Typography>
                  )}
                </AccordionDetails>
              </Accordion>

              {/* Ranked Candidates Section */}
              <Card sx={{ p: 3, bgcolor: "background.paper", border: "1px solid rgba(255,255,255,0.08)" }}>
                <Box sx={{ display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: 2, mb: 2.5 }}>
                  <Box>
                    <Typography variant="h6" sx={{ fontWeight: 700 }}>
                      Ranked Candidates ({slateDetail.candidates?.length || 0})
                    </Typography>
                    <Typography variant="caption" sx={{ color: "text.secondary" }}>
                      Highest expected value props filtered and scored across all sports.
                    </Typography>
                  </Box>

                  <Button
                    variant="outlined"
                    color="primary"
                    size="small"
                    onClick={handleCheckAvailability}
                    disabled={checkingAvail || !slateDetail.candidates || slateDetail.candidates.length === 0}
                    startIcon={checkingAvail ? <CircularProgress size={14} color="inherit" /> : <Zap size={14} />}
                    sx={{ fontWeight: 700 }}
                  >
                    Check Availability
                  </Button>
                </Box>

                {availError && <Alert severity="warning" sx={{ mb: 2 }}>{availError}</Alert>}

                {(!slateDetail.candidates || slateDetail.candidates.length === 0) ? (
                  <Alert severity="warning">
                    No actionable picks found. All match pipelines either failed or produced no viable candidates.
                  </Alert>
                ) : (
                  <Box sx={{ display: "flex", flexDirection: "column", gap: 2 }}>
                    {slateDetail.candidates.map((candidate, idx) => {
                      const player = candidate.subject_name || candidate.player || "Unknown";
                      const market = candidate.market || "Unknown";
                      const key = `${player.toLowerCase()}-${market.toLowerCase()}`;
                      const badge = availBadges[key];

                      return (
                        <SlateCandidateCard
                          key={idx}
                          candidate={candidate}
                          badge={badge}
                        />
                      );
                    })}
                  </Box>
                )}
              </Card>

              {/* Match Runs Details Expander */}
              {slateDetail.match_runs && slateDetail.match_runs.length > 0 && (
                <Accordion sx={{ bgcolor: "background.paper", border: "1px solid rgba(255,255,255,0.08)" }}>
                  <AccordionSummary expandIcon={<ChevronDown size={18} color="#94A3B8" />}>
                    <Typography variant="subtitle2" sx={{ fontWeight: 700 }}>
                      Match Run Details ({slateDetail.match_runs.length})
                    </Typography>
                  </AccordionSummary>
                  <AccordionDetails>
                    <Box sx={{ display: "flex", flexDirection: "column", gap: 1 }}>
                      {slateDetail.match_runs.map((r, idx) => (
                        <Paper
                          key={idx}
                          elevation={0}
                          sx={{ p: 1.5, bgcolor: "rgba(0,0,0,0.2)", border: "1px solid rgba(255,255,255,0.05)", borderRadius: "6px" }}
                        >
                          <Typography variant="body2" sx={{ fontFamily: "monospace", fontSize: "0.8rem" }}>
                            [{r.sport}] {r.home_team} vs {r.away_team} — {r.status}, {r.pick_count} picks ({r.latency_ms}ms)
                          </Typography>
                          {r.error_message && (
                            <Typography variant="caption" sx={{ color: "error.main", display: "block", mt: 0.5 }}>
                              {r.error_message}
                            </Typography>
                          )}
                          {r.operation_id && (
                            <Button
                              size="small"
                              startIcon={<Activity size={14} />}
                              sx={{ mt: 0.75 }}
                              onClick={() => {
                                if (onNavigateToDiagnostics) {
                                  onNavigateToDiagnostics(r.operation_id!);
                                } else {
                                  window.location.hash = `diagnostics?operation=${encodeURIComponent(r.operation_id!)}`;
                                }
                              }}
                            >
                              View diagnostics
                            </Button>
                          )}
                        </Paper>
                      ))}
                    </Box>
                  </AccordionDetails>
                </Accordion>
              )}
            </Box>
          )}
        </Box>
      </Box>
    </Box>
  );
};
