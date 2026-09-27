import { createTheme } from "@mui/material/styles";

export const darkTheme = createTheme({
  palette: {
    mode: "dark",
    background: {
      default: "#070B14",
      paper: "#0D1322",
    },
    primary: {
      main: "#06B6D4", // Cyan
      light: "#38BDF8",
      dark: "#0891B2",
      contrastText: "#FFFFFF",
    },
    secondary: {
      main: "#3B82F6", // Blue
      light: "#60A5FA",
      dark: "#2563EB",
    },
    success: {
      main: "#10B981", // Emerald green for EV+
      light: "#34D399",
      dark: "#059669",
    },
    warning: {
      main: "#F59E0B", // Amber for caution
      light: "#FBBF24",
      dark: "#D97706",
    },
    error: {
      main: "#F43F5E", // Rose red for high risk
      light: "#FB7185",
      dark: "#E11D48",
    },
    divider: "#1E293B",
    text: {
      primary: "#F8FAFC",
      secondary: "#94A3B8",
      disabled: "#64748B",
    },
  },
  typography: {
    fontFamily: "'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif",
    h1: { fontWeight: 800, letterSpacing: "-0.03em" },
    h2: { fontWeight: 800, letterSpacing: "-0.025em" },
    h3: { fontWeight: 700, letterSpacing: "-0.02em" },
    h4: { fontWeight: 700, letterSpacing: "-0.015em" },
    h5: { fontWeight: 700 },
    h6: { fontWeight: 600 },
    subtitle1: { color: "#94A3B8" },
    subtitle2: { color: "#94A3B8", fontWeight: 500 },
    body1: { fontSize: "0.925rem", lineHeight: 1.6 },
    body2: { fontSize: "0.85rem", color: "#94A3B8" },
    button: { textTransform: "none", fontWeight: 600 },
  },
  shape: {
    borderRadius: 10,
  },
  components: {
    MuiCard: {
      styleOverrides: {
        root: {
          backgroundColor: "#131B2E",
          backgroundImage: "none",
          border: "1px solid #1E293B",
          borderRadius: 12,
          transition: "all 0.2s ease",
          "&:hover": {
            borderColor: "rgba(6, 182, 212, 0.4)",
            boxShadow: "0 8px 24px -4px rgba(0, 0, 0, 0.5), 0 0 12px rgba(6, 182, 212, 0.15)",
          },
        },
      },
    },
    MuiPaper: {
      styleOverrides: {
        root: {
          backgroundImage: "none",
          border: "1px solid #1E293B",
        },
      },
    },
    MuiButton: {
      styleOverrides: {
        root: {
          borderRadius: 8,
          fontWeight: 600,
          padding: "8px 16px",
        },
        containedPrimary: {
          background: "linear-gradient(135deg, #06B6D4, #3B82F6)",
          boxShadow: "0 2px 10px rgba(6, 182, 212, 0.3)",
          "&:hover": {
            background: "linear-gradient(135deg, #0891B2, #2563EB)",
            boxShadow: "0 4px 15px rgba(6, 182, 212, 0.4)",
          },
        },
      },
    },
    MuiChip: {
      styleOverrides: {
        root: {
          fontWeight: 600,
          borderRadius: 6,
        },
      },
    },
    MuiTextField: {
      styleOverrides: {
        root: {
          "& .MuiOutlinedInput-root": {
            backgroundColor: "#0D1322",
            "& fieldset": { borderColor: "#1E293B" },
            "&:hover fieldset": { borderColor: "#334155" },
            "&.Mui-focused fieldset": { borderColor: "#06B6D4" },
          },
        },
      },
    },
  },
});
