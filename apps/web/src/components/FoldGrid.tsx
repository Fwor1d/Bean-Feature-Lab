"use client";

import Link from "next/link";
import { Box } from "@mui/material";
import { ruRU } from "@mui/x-data-grid/locales";
import { DataGrid, type GridColDef } from "@mui/x-data-grid";
import type { FoldResult } from "@/lib/api/contracts";
import { metric } from "@/lib/science";

export function FoldGrid({ runId, folds }: { runId: number; folds: FoldResult[] }) {
  const columns: GridColDef<FoldResult>[] = [
    { field: "fold_id", headerName: "Outer fold", width: 132, renderCell: ({ value }) => <Link href={`/runs/${runId}?fold=${value}`}>{value}</Link> },
    { field: "train_size", headerName: "Train", width: 104, type: "number" },
    { field: "test_size", headerName: "Test", width: 100, type: "number" },
    { field: "macro_f1", headerName: "Macro-F1", width: 125, type: "number", valueFormatter: value => metric(value) },
    { field: "accuracy", headerName: "Accuracy", width: 116, type: "number", valueFormatter: value => metric(value) },
    { field: "search_seconds", headerName: "Search, с", width: 112, type: "number", valueFormatter: value => metric(value, 2) },
    { field: "refit_seconds", headerName: "Refit, с", width: 105, type: "number", valueFormatter: value => metric(value, 2) },
    { field: "selected_original_features", headerName: "Признаки", minWidth: 260, flex: 1, renderCell: ({ row }) => row.selected_original_features?.join(", ") ?? "PCA / не применимо" },
  ];
  return <Box sx={{ width: "100%", minHeight: 230 }}><DataGrid rows={folds} columns={columns} getRowId={row => row.fold_id}
    localeText={ruRU.components.MuiDataGrid.defaultProps.localeText} density="compact" disableRowSelectionOnClick initialState={{ pagination: { paginationModel: { pageSize: 15 } } }}
    pageSizeOptions={[15, 30]} sx={{ border: 0, "& .MuiDataGrid-cell": { fontVariantNumeric: "tabular-nums" } }} /></Box>;
}
