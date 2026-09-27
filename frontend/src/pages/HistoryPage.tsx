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
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Paper,
  CircularProgress,
  Alert,
  Accordion,
  AccordionSummary,
  AccordionDetails,
  Divider,
  Chip,
} from "@mui/material";
import {
  ChevronDown,
  ChevronLeft,
  ChevronRight,
  Activity,
  Save,
  CheckCircle2,
  Trophy,
  History as HistoryIcon,
  RotateCcw,
} from "lucide-react";
import { api } from "../api/client";
import { HitRateSummary, OutcomeRecord, PickDetail, PickSummary } from "../api/types";
import { MarkdownRenderer } from "../components/Common/MarkdownRenderer";
import { isRecord, loadPageDraft, savePageDraft } from "../state/pageDrafts";
import { runState } from "../state/runStatus";
import { pickNflRecommendationSummary } from "../state/nflRecommendation";

type OutcomeResult = "win" | "loss" | "push" | "void";
type HistoryDraft = { sportFilter: string; pageSize: number; page: number; selectedId: string | null; gradingDrafts: Record<string, Partial<Record<number, OutcomeResult>>> };
const defaultHistoryDraft = (): HistoryDraft => ({ sportFilter: "All", pageSize: 20, page: 0, selectedId: null, gradingDrafts: {} });
const isHistoryDraft = (value: unknown): value is HistoryDraft => isRecord(value) && typeof value.sportFilter === "string" && typeof value.pageSize === "number" && typeof value.page === "number" && (typeof value.selectedId === "string" || value.selectedId === null) && isRecord(value.gradingDrafts);

function formatHistoryRow(item: PickSummary): string {
  const parts: string[] = [];
  if (item.created_at) parts.push(item.created_at);
  if (item.display_title) parts.push(item.display_title);
  if (item.sport) parts.push(`[${item.sport}]`);
  if (item.competition) parts.push(`[${item.competition}]`);
  if (item.fixture_status) parts.push(`fixture=${item.fixture_status}`);
  if (item.llm_status && item.llm_status !== "not_requested") {
    parts.push(`llm=${item.llm_status}`);
  }
  return parts.join(" · ");
}

interface HistoryPageProps {
  onNavigateToDiagnostics?: (operationId: string) => void;
}

export const HistoryPage: React.FC<HistoryPageProps> = ({ onNavigateToDiagnostics }) => {
  const [initialDraft] = useState(() => loadPageDraft("history", defaultHistoryDraft(), isHistoryDraft));
  // ---- Filter & Pagination State ----
  const [sportFilter, setSportFilter] = useState<string>(initialDraft.sportFilter);
  const [pageSize, setPageSize] = useState<number>(initialDraft.pageSize);
  const [page, setPage] = useState<number>(initialDraft.page);

  // ---- Data State ----
  const [loadingList, setLoadingList] = useState<boolean>(false);
  const [picks, setPicks] = useState<PickSummary[]>([]);
  const [listError, setListError] = useState<string | null>(null);

  // ---- Selection State ----
  const [selectedId, setSelectedId] = useState<string | null>(initialDraft.selectedId);
  const [loadingDetail, setLoadingDetail] = useState<boolean>(false);
  const [pickDetail, setPickDetail] = useState<PickDetail | null>(null);
  const [detailError, setDetailError] = useState<string | null>(null);

  // ---- Outcomes Grading State ----
  const [existingOutcomes, setExistingOutcomes] = useState<OutcomeRecord[]>([]);
  const [gradingValues, setGradingValues] = useState<Partial<Record<number, OutcomeResult>>>({});
  const [gradingDrafts, setGradingDrafts] = useState<HistoryDraft["gradingDrafts"]>(initialDraft.gradingDrafts);
  const [savingOutcomes, setSavingOutcomes] = useState<boolean>(false);
  const [outcomeSuccess, setOutcomeSuccess] = useState<string | null>(null);
  const [outcomeError, setOutcomeError] = useState<string | null>(null);

  // ---- Hit Rate State ----
  const [hitRate, setHitRate] = useState<HitRateSummary | null>(null);
  const detailRequestRef = useRef(0);

  useEffect(() => {
    savePageDraft("history", { sportFilter, pageSize, page, selectedId, gradingDrafts });
  }, [sportFilter, pageSize, page, selectedId, gradingDrafts]);

  // Load list whenever filters/page change
  useEffect(() => {
    loadPicksList();
  }, [sportFilter, page, pageSize]);

  // Load hit rate on mount & when outcomes change
  useEffect(() => {
    loadHitRate();
  }, []);

  const loadHitRate = async () => {
    try {
      const data = await api.getHitRate();
      setHitRate(data);
    } catch {
      // Ignored or null
    }
  };

  const loadPicksList = async () => {
    setLoadingList(true);
    setListError(null);
    try {
      const sportParam = sportFilter !== "All" ? sportFilter.toLowerCase() : undefined;
      const resp = await api.listPicks(pageSize, page * pageSize, sportParam);
      const items = resp.items || [];
      setPicks(items);

      // Auto-select first item if none selected or if previously selected item is no longer visible
      if (items.length > 0) {
        if (!selectedId || !items.some((it) => it.id === selectedId)) {
          handleSelectPick(items[0].id);
        }
      } else {
        setSelectedId(null);
        setPickDetail(null);
      }
    } catch (err: any) {
      setListError(err.message || "Failed to load pick history");
    } finally {
      setLoadingList(false);
    }
  };

  const handleSelectPick = async (id: string) => {
    const requestId = detailRequestRef.current + 1;
    detailRequestRef.current = requestId;
    setSelectedId(id);
    setLoadingDetail(true);
    setDetailError(null);
    setOutcomeSuccess(null);
    setOutcomeError(null);

    try {
      const detail = await api.getPick(id);
      if (detailRequestRef.current !== requestId) return;
      setPickDetail(detail);

      // Fetch existing outcomes
      try {
        const outcomesResp = await api.getOutcomes(id);
        if (detailRequestRef.current !== requestId) return;
        const outcomes = outcomesResp.items || [];
        setExistingOutcomes(outcomes);

        // Pre-fill grading values if existing
        const initialGrading: Partial<Record<number, OutcomeResult>> = {};
        outcomes.forEach((o) => {
          initialGrading[o.rank] = o.result;
        });
        setGradingValues({ ...initialGrading, ...(gradingDrafts[id] || {}) });
      } catch {
        if (detailRequestRef.current !== requestId) return;
        setExistingOutcomes([]);
        setGradingValues({});
      }
    } catch (err: any) {
      if (detailRequestRef.current !== requestId) return;
      setDetailError(err.message || "Failed to load pick details");
    } finally {
      if (detailRequestRef.current === requestId) setLoadingDetail(false);
    }
  };

  const handleSaveOutcomes = async () => {
    if (!selectedId || !pickDetail?.scores) return;
    setOutcomeSuccess(null);
    setOutcomeError(null);

    const recordedByRank = new Map(existingOutcomes.map((outcome) => [outcome.rank, outcome.result]));
    const rows: OutcomeRecord[] = pickDetail.scores.flatMap((score, idx) => {
      const rank = score.rank || idx + 1;
      const result = gradingValues[rank];
      if (!result || recordedByRank.get(rank) === result) return [];
      const player = score.subject_name || score.player || score.name || "Unknown";
      const market = score.market || score.prop || "Unknown";
      return { rank, player, market, result };
    });

    if (rows.length === 0) {
      setOutcomeSuccess("No outcome changes to save.");
      return;
    }

    setSavingOutcomes(true);

    try {
      const resp = await api.recordOutcomes(selectedId, rows);
      const updatedByRank = new Map(existingOutcomes.map((outcome) => [outcome.rank, outcome]));
      for (const outcome of resp.items || rows) {
        updatedByRank.set(outcome.rank, outcome);
      }
      const updatedOutcomes = Array.from(updatedByRank.values()).sort((a, b) => a.rank - b.rank);
      setExistingOutcomes(updatedOutcomes);
      setGradingValues(Object.fromEntries(updatedOutcomes.map((outcome) => [outcome.rank, outcome.result])));
      setGradingDrafts((drafts) => {
        const next = { ...drafts };
        delete next[selectedId];
        return next;
      });
      setOutcomeSuccess("Outcomes successfully saved.");
      loadHitRate(); // Refresh hit rate metrics
    } catch (err: any) {
      setOutcomeError(err.message || "Failed to record outcomes.");
    } finally {
      setSavingOutcomes(false);
    }
  };

  const hasOutcomeChanges = Boolean(
    pickDetail?.scores?.some((score, idx) => {
      const rank = score.rank || idx + 1;
      const result = gradingValues[rank];
      return result && result !== existingOutcomes.find((outcome) => outcome.rank === rank)?.result;
    })
  );

  return (
    <Box sx={{ display: "flex", flexDirection: "column", gap: 3.5, pb: 6 }}>
      {/* Page Header */}
      <Box sx={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", flexWrap: "wrap", gap: 2 }}>
        <Box>
          <Typography variant="h4" sx={{ fontWeight: 800, letterSpacing: "-0.02em", color: "#FFF" }}>
            Pick History
          </Typography>
          <Typography variant="body2" sx={{ color: "text.secondary", mt: 0.5 }}>
            Recent pipeline runs persisted in the database with outcome grading and hit-rate analytics.
          </Typography>
        </Box>

        {/* Hit Rate Metric Header Card */}
        {hitRate && (
          <Card
            sx={{
              p: 2,
              bgcolor: "background.paper",
              border: "1px solid rgba(6, 182, 212, 0.3)",
              display: "flex",
              alignItems: "center",
              gap: 2.5,
            }}
          >
            <Box sx={{ display: "flex", alignItems: "center", gap: 1 }}>
              <Trophy size={28} color="#06B6D4" />
              <Box>
                <Typography variant="caption" sx={{ color: "text.secondary", textTransform: "uppercase", fontWeight: 700 }}>
                  Win Rate
                </Typography>
                <Typography variant="h5" sx={{ fontWeight: 800, color: "success.main", fontFamily: "monospace" }}>
                  {hitRate.hit_rate != null ? `${(hitRate.hit_rate * 100).toFixed(1)}%` : "—"}
                </Typography>
              </Box>
            </Box>

            <Divider orientation="vertical" flexItem sx={{ borderColor: "rgba(255,255,255,0.1)" }} />

            <Box>
              <Typography variant="body2" sx={{ fontWeight: 700 }}>
                {hitRate.totals.win}W / {hitRate.totals.loss}L of {hitRate.decided}
              </Typography>
              {(hitRate.totals.push || hitRate.totals.void) && (
                <Typography variant="caption" sx={{ color: "text.secondary" }}>
                  push: {hitRate.totals.push || 0} · void: {hitRate.totals.void || 0}
                </Typography>
              )}
            </Box>
          </Card>
        )}
      </Box>

      {/* Main Grid: Left Controls & List, Right Detail */}
      <Box sx={{ display: "grid", gridTemplateColumns: { xs: "1fr", lg: "380px 1fr" }, gap: 3, alignItems: "start" }}>
        {/* Left Column: Filter, Pagination & Run List */}
        <Box sx={{ display: "flex", flexDirection: "column", gap: 2 }}>
          <Card sx={{ p: 2.5, bgcolor: "background.paper", border: "1px solid rgba(255,255,255,0.08)" }}>
            <Typography variant="subtitle2" sx={{ fontWeight: 700, mb: 2 }}>
              Filters & Pagination
            </Typography>

            <Box sx={{ display: "flex", flexDirection: "column", gap: 2 }}>
              <FormControl fullWidth size="small">
                <InputLabel>Filter by sport</InputLabel>
                <Select
                  value={sportFilter}
                  label="Filter by sport"
                  onChange={(e) => {
                    setSportFilter(e.target.value);
                    setPage(0);
                  }}
                >
                  <MenuItem value="All">All</MenuItem>
                  <MenuItem value="Soccer">Soccer</MenuItem>
                  <MenuItem value="Basketball">Basketball</MenuItem>
                  <MenuItem value="Baseball">Baseball</MenuItem>
                  <MenuItem value="NFL">NFL</MenuItem>
                </Select>
              </FormControl>

              <Box sx={{ px: 1 }}>
                <Typography variant="caption" sx={{ color: "text.secondary" }}>
                  Page size: <strong>{pageSize}</strong>
                </Typography>
                <Slider
                  value={pageSize}
                  onChange={(_, val) => {
                    setPageSize(val as number);
                    setPage(0);
                  }}
                  min={5}
                  max={50}
                  step={5}
                  size="small"
                  valueLabelDisplay="auto"
                />
              </Box>

              <Box sx={{ display: "flex", justifyContent: "space-between", alignItems: "center", pt: 0.5 }}>
                <Button
                  variant="outlined"
                  size="small"
                  disabled={page === 0}
                  onClick={() => setPage(Math.max(0, page - 1))}
                  startIcon={<ChevronLeft size={16} />}
                >
                  Prev
                </Button>
                <Typography variant="caption" sx={{ color: "text.secondary", fontWeight: 700 }}>
                  Page {page + 1}
                </Typography>
                <Button
                  variant="outlined"
                  size="small"
                  disabled={picks.length < pageSize}
                  onClick={() => setPage(page + 1)}
                  endIcon={<ChevronRight size={16} />}
                >
                  Next
                </Button>
              </Box>
            </Box>
          </Card>

          {/* Runs List */}
          <Card sx={{ bgcolor: "background.paper", border: "1px solid rgba(255,255,255,0.08)", overflow: "hidden" }}>
            <Box sx={{ p: 2, borderBottom: "1px solid rgba(255,255,255,0.08)", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
              <Typography variant="subtitle2" sx={{ fontWeight: 700 }}>
                Past Runs ({picks.length})
              </Typography>
              <Button size="small" onClick={loadPicksList} startIcon={<RotateCcw size={14} />}>
                Refresh
              </Button>
            </Box>

            {loadingList ? (
              <Box sx={{ p: 4, textAlign: "center" }}>
                <CircularProgress size={24} />
              </Box>
            ) : listError ? (
              <Box sx={{ p: 2 }}>
                <Alert severity="error">{listError}</Alert>
              </Box>
            ) : picks.length === 0 ? (
              <Box sx={{ p: 3, textAlign: "center" }}>
                <Typography variant="body2" sx={{ color: "text.secondary" }}>
                  No picks yet on this page.
                </Typography>
              </Box>
            ) : (
              <Box sx={{ maxHeight: 600, overflowY: "auto", display: "flex", flexDirection: "column" }}>
                {picks.map((item) => {
                  const isSelected = item.id === selectedId;
                  return (
                    <Box
                      key={item.id}
                      onClick={() => handleSelectPick(item.id)}
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
                        {item.created_at}
                      </Typography>
                      <Typography variant="body2" sx={{ fontWeight: 700, color: isSelected ? "#06B6D4" : "#FFF", mt: 0.3 }}>
                        {item.display_title}
                      </Typography>
                      <Box sx={{ display: "flex", alignItems: "center", gap: 1, mt: 0.8, flexWrap: "wrap" }}>
                        {item.sport && (
                          <Chip label={item.sport} size="small" sx={{ fontSize: "0.68rem", height: 20, bgcolor: "rgba(255,255,255,0.08)" }} />
                        )}
                        <Chip
                          label={runState(item).label}
                          size="small"
                          color={runState(item).color}
                          sx={{ fontSize: "0.68rem", height: 20 }}
                        />
                      </Box>
                    </Box>
                  );
                })}
              </Box>
            )}
          </Card>
        </Box>

        {/* Right Column: Selected Pick Inspection & Outcome Grading */}
        <Box>
          {loadingDetail ? (
            <Card sx={{ p: 6, textAlign: "center", bgcolor: "background.paper" }}>
              <CircularProgress size={32} />
              <Typography variant="body2" sx={{ color: "text.secondary", mt: 2 }}>
                Loading pick details...
              </Typography>
            </Card>
          ) : detailError ? (
            <Alert severity="error">{detailError}</Alert>
          ) : !pickDetail ? (
            <Card sx={{ p: 6, textAlign: "center", bgcolor: "background.paper", borderStyle: "dashed" }}>
              <HistoryIcon size={40} color="#64748B" style={{ marginBottom: 12 }} />
              <Typography variant="h6" sx={{ color: "text.secondary" }}>
                Select a past run from the list to view its stored report & grade outcomes
              </Typography>
            </Card>
          ) : (
            <Box sx={{ display: "flex", flexDirection: "column", gap: 3 }}>
              {/* Run Metadata Header */}
              <Paper
                elevation={0}
                sx={{
                  p: 2.5,
                  bgcolor: "background.paper",
                  border: "1px solid rgba(255,255,255,0.08)",
                  borderRadius: "8px",
                  display: "flex",
                  justifyContent: "space-between",
                  alignItems: "flex-start",
                  flexWrap: "wrap",
                  gap: 2,
                }}
              >
                <Box>
                  <Typography variant="h6" sx={{ fontWeight: 800, color: "#FFF" }}>
                    {pickDetail.display_title}
                  </Typography>
                  <Typography variant="caption" sx={{ color: "text.secondary" }}>
                    id <code>{pickDetail.id}</code> · status <code>{pickDetail.status}</code> · created {pickDetail.created_at} · latency {pickDetail.latency_ms ?? "—"} ms
                  </Typography>
                </Box>

                {pickDetail.operation_id && (
                  <Button
                    variant="outlined"
                    size="small"
                    startIcon={<Activity size={14} />}
                    onClick={() => {
                      if (onNavigateToDiagnostics && pickDetail.operation_id) {
                        onNavigateToDiagnostics(pickDetail.operation_id);
                      } else {
                        window.location.hash = "diagnostics";
                      }
                    }}
                  >
                    View Diagnostics
                  </Button>
                )}
              </Paper>

              {pickDetail.status === "failed" && (
                <Alert severity="error">
                  Pipeline failed at stage <strong>{pickDetail.error_stage || "unknown"}</strong>: {pickDetail.error_message || "Unknown error"}
                </Alert>
              )}

              {pickDetail.sport === "nfl" && pickNflRecommendationSummary(pickDetail) && (
                <Alert severity={pickDetail.outcome === "no_picks" ? "info" : "warning"}>{pickNflRecommendationSummary(pickDetail)!.message}</Alert>
              )}

              {/* Original Request JSON Expander */}
              {pickDetail.request && (
                <Accordion sx={{ bgcolor: "background.paper", border: "1px solid rgba(255,255,255,0.08)" }}>
                  <AccordionSummary expandIcon={<ChevronDown size={18} color="#94A3B8" />}>
                    <Typography variant="subtitle2" sx={{ fontWeight: 700 }}>
                      Original Request
                    </Typography>
                  </AccordionSummary>
                  <AccordionDetails>
                    <Box sx={{ bgcolor: "#070B14", p: 2, borderRadius: "6px", overflowX: "auto" }}>
                      <pre style={{ margin: 0, fontFamily: "monospace", fontSize: "0.8rem", color: "#E2E8F0" }}>
                        {JSON.stringify(pickDetail.request, null, 2)}
                      </pre>
                    </Box>
                  </AccordionDetails>
                </Accordion>
              )}

              {/* Stored Markdown Report */}
              {pickDetail.report_markdown && (
                <Card sx={{ p: 3.5, bgcolor: "background.paper", border: "1px solid rgba(255,255,255,0.08)" }}>
                  <MarkdownRenderer content={pickDetail.report_markdown} />
                </Card>
              )}

              {/* Trace JSON Expander */}
              {pickDetail.trace && (
                <Accordion sx={{ bgcolor: "background.paper", border: "1px solid rgba(255,255,255,0.08)" }}>
                  <AccordionSummary expandIcon={<ChevronDown size={18} color="#94A3B8" />}>
                    <Typography variant="subtitle2" sx={{ fontWeight: 700 }}>
                      Trace
                    </Typography>
                  </AccordionSummary>
                  <AccordionDetails>
                    <Box sx={{ bgcolor: "#070B14", p: 2, borderRadius: "6px", overflowX: "auto" }}>
                      <pre style={{ margin: 0, fontFamily: "monospace", fontSize: "0.8rem", color: "#E2E8F0" }}>
                        {JSON.stringify(pickDetail.trace, null, 2)}
                      </pre>
                    </Box>
                  </AccordionDetails>
                </Accordion>
              )}

              {/* Match Inputs JSON Expander */}
              {pickDetail.match_inputs && (
                <Accordion sx={{ bgcolor: "background.paper", border: "1px solid rgba(255,255,255,0.08)" }}>
                  <AccordionSummary expandIcon={<ChevronDown size={18} color="#94A3B8" />}>
                    <Typography variant="subtitle2" sx={{ fontWeight: 700 }}>
                      Match Inputs
                    </Typography>
                  </AccordionSummary>
                  <AccordionDetails>
                    <Box sx={{ bgcolor: "#070B14", p: 2, borderRadius: "6px", overflowX: "auto" }}>
                      <pre style={{ margin: 0, fontFamily: "monospace", fontSize: "0.8rem", color: "#E2E8F0" }}>
                        {JSON.stringify(pickDetail.match_inputs, null, 2)}
                      </pre>
                    </Box>
                  </AccordionDetails>
                </Accordion>
              )}

              {/* ========================================================================= */}
              {/* OUTCOME GRADING SECTION (Exact Streamlit Parity)                          */}
              {/* ========================================================================= */}
              {pickDetail.status === "success" && (
                <Card sx={{ p: 3, bgcolor: "background.paper", border: "1px solid rgba(255,255,255,0.08)" }}>
                  <Typography variant="h6" sx={{ fontWeight: 700, mb: 0.5 }}>
                    Outcomes & Grading
                  </Typography>
                  <Typography variant="caption" sx={{ color: "text.secondary", display: "block", mb: 2 }}>
                    Grade each prop pick after match settlement to update historical hit-rate statistics.
                  </Typography>

                  {/* Previously Graded Outcomes Table */}
                  {existingOutcomes.length > 0 && (
                    <Box sx={{ mb: 3 }}>
                      <Typography variant="caption" sx={{ color: "primary.main", fontWeight: 700, mb: 1, display: "block" }}>
                        {existingOutcomes.length} outcome(s) already recorded:
                      </Typography>
                      <TableContainer component={Paper} elevation={0} sx={{ bgcolor: "rgba(0,0,0,0.3)", border: "1px solid rgba(255,255,255,0.06)" }}>
                        <Table size="small">
                          <TableHead>
                            <TableRow>
                              <TableCell sx={{ color: "text.secondary", fontWeight: 700 }}>Rank</TableCell>
                              <TableCell sx={{ color: "text.secondary", fontWeight: 700 }}>Player</TableCell>
                              <TableCell sx={{ color: "text.secondary", fontWeight: 700 }}>Market</TableCell>
                              <TableCell sx={{ color: "text.secondary", fontWeight: 700 }}>Result</TableCell>
                              <TableCell sx={{ color: "text.secondary", fontWeight: 700 }}>Recorded At</TableCell>
                            </TableRow>
                          </TableHead>
                          <TableBody>
                            {existingOutcomes.map((row, idx) => (
                              <TableRow key={idx}>
                                <TableCell>#{row.rank}</TableCell>
                                <TableCell sx={{ fontWeight: 600 }}>{row.player}</TableCell>
                                <TableCell>{row.market}</TableCell>
                                <TableCell>
                                  <Chip
                                    label={row.result.toUpperCase()}
                                    size="small"
                                    color={
                                      row.result === "win"
                                        ? "success"
                                        : row.result === "loss"
                                        ? "error"
                                        : "default"
                                    }
                                    sx={{ fontWeight: 700, fontSize: "0.7rem", height: 22 }}
                                  />
                                </TableCell>
                                <TableCell sx={{ fontFamily: "monospace", fontSize: "0.75rem", color: "text.secondary" }}>
                                  {row.recorded_at || "—"}
                                </TableCell>
                              </TableRow>
                            ))}
                          </TableBody>
                        </Table>
                      </TableContainer>
                    </Box>
                  )}

                  {/* Interactive Grading Form */}
                  {(!pickDetail.scores || pickDetail.scores.length === 0) ? (
                    <Alert severity="info">No scored picks to grade in this run.</Alert>
                  ) : (
                    <Box sx={{ display: "flex", flexDirection: "column", gap: 2 }}>
                      {outcomeSuccess && <Alert severity="success">{outcomeSuccess}</Alert>}
                      {outcomeError && <Alert severity="error">{outcomeError}</Alert>}

                      <Box sx={{ display: "flex", flexDirection: "column", gap: 1.5 }}>
                        {pickDetail.scores.map((score, idx) => {
                          const rank = score.rank || idx + 1;
                          const player = score.subject_name || score.player || score.name || "Unknown";
                          const market = score.market || score.prop || "Unknown";
                          const currentVal = gradingValues[rank] || "";

                          return (
                            <Paper
                              key={rank}
                              elevation={0}
                              sx={{
                                p: 1.5,
                                bgcolor: "rgba(0,0,0,0.25)",
                                border: "1px solid rgba(255,255,255,0.06)",
                                borderRadius: "8px",
                                display: "flex",
                                justifyContent: "space-between",
                                alignItems: "center",
                                gap: 2,
                              }}
                            >
                              <Box>
                                <Typography variant="body2" sx={{ fontWeight: 700 }}>
                                  #{rank} · {player} · {market}
                                </Typography>
                                {score.line != null && (
                                  <Typography variant="caption" sx={{ color: "text.secondary" }}>
                                    Line: {score.line} ({score.direction || "over"}) · Odds: {score.odds || "—"}
                                  </Typography>
                                )}
                              </Box>

                              <FormControl size="small" sx={{ minWidth: 120 }}>
                                <Select
                                  value={currentVal}
                                  displayEmpty
                                  inputProps={{ "aria-label": `Outcome for rank ${rank}` }}
                                  onChange={(e) => {
                                    const result = e.target.value as OutcomeResult;
                                    setGradingValues((prev) => {
                                      const next = { ...prev, [rank]: result };
                                      if (selectedId) {
                                        setGradingDrafts((drafts) => ({ ...drafts, [selectedId]: next }));
                                      }
                                      return next;
                                    });
                                  }}
                                >
                                  <MenuItem value="" disabled>
                                    <em>Select outcome</em>
                                  </MenuItem>
                                  <MenuItem value="win">win</MenuItem>
                                  <MenuItem value="loss">loss</MenuItem>
                                  <MenuItem value="push">push</MenuItem>
                                  <MenuItem value="void">void</MenuItem>
                                </Select>
                              </FormControl>
                            </Paper>
                          );
                        })}
                      </Box>

                      <Button
                        variant="contained"
                        color="primary"
                        onClick={handleSaveOutcomes}
                        disabled={savingOutcomes || !hasOutcomeChanges}
                        startIcon={savingOutcomes ? <CircularProgress size={16} color="inherit" /> : <Save size={16} />}
                        sx={{ alignSelf: "flex-start", mt: 1, fontWeight: 700 }}
                      >
                        {savingOutcomes ? "Saving Outcomes..." : "Save outcomes"}
                      </Button>
                    </Box>
                  )}
                </Card>
              )}
            </Box>
          )}
        </Box>
      </Box>
    </Box>
  );
};
