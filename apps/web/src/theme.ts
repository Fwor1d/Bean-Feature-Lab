"use client";

import { createTheme } from "@mui/material/styles";

export const theme = createTheme({
  palette: {
    primary: { main: "#2e6bd3" },
    background: { default: "#eef1f4", paper: "#ffffff" },
    text: { primary: "#182533", secondary: "#546475" },
    divider: "#d8e0e8",
  },
  typography: { fontFamily: '"Golos Text", Arial, sans-serif', fontSize: 14 },
  shape: { borderRadius: 5 },
  components: {
    MuiButton: { defaultProps: { disableElevation: true }, styleOverrides: { root: { textTransform: "none", fontWeight: 600 } } },
    MuiTextField: { defaultProps: { size: "small" } },
    MuiSelect: { defaultProps: { size: "small" } },
  },
});
