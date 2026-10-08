"use client";

import Link from "next/link";
import { Box, Chip } from "@mui/material";
import { ruRU } from "@mui/x-data-grid/locales";
import { DataGrid, type GridColDef } from "@mui/x-data-grid";
import type { RunStatus } from "@/lib/api/contracts";
import { metric, runLabel, utcTime } from "@/lib/science";

export interface RunGridRow {
  id: number;
  displayId: string;
  model: string;
  selector: string;
  budget: string;
  status: RunStatus;
  macroF1: number | null;
  accuracy: number | null;
  folds: number | null;
  created: string;
  finished: string | null;
}

const columns: GridColDef<RunGridRow>[] = [
  { field: "displayId", headerName: "Run ID", width: 124, renderCell: ({ row }) => <Link href={`/runs/${row.id}`}>{row.displayId}</Link> },
  { field: "macroF1", headerName: "Macro-F1", width: 101, type: "number", valueFormatter: value => metric(value) },
  { field: "accuracy", headerName: "Accuracy", width: 98, type: "number", valueFormatter: value => metric(value) },
  { field: "status", headerName: "Исполнение", width: 140, renderCell: ({ value }) => <Chip size="small" variant="outlined" label={runLabel[value as RunStatus]} color={value === "FAILED" ? "error" : value === "COMPLETED" ? "success" : value === "RUNNING" ? "info" : "default"} /> },
  { field: "model", headerName: "Модель", minWidth: 160, flex: 1 },
  { field: "selector", headerName: "Метод", minWidth: 158, flex: 1 },
  { field: "budget", headerName: "Бюджет", width: 126 },
  { field: "folds", headerName: "Outer folds", width: 112, type: "number", valueFormatter: value => value ?? "—" },
  { field: "created", headerName: "Создан", minWidth: 168, valueFormatter: value => utcTime(value) },
  { field: "finished", headerName: "Завершён", minWidth: 168, valueFormatter: value => utcTime(value) },
];

export function RunsGrid({ rows }: { rows: RunGridRow[] }) {
  return <Box sx={{ width: "100%", minHeight: 260 }}><p className="grid-scroll-note">Для остальных колонок прокрутите таблицу вправо →</p><DataGrid rows={rows} columns={columns}
    density="compact" disableRowSelectionOnClick initialState={{ pagination: { paginationModel: { pageSize: 10 } } }}
    pageSizeOptions={[10, 25, 50]} localeText={{ ...ruRU.components.MuiDataGrid.defaultProps.localeText, noRowsLabel: "Запусков пока нет" }}
    sx={{ border: 0, "& .MuiDataGrid-cell": { fontVariantNumeric: "tabular-nums" } }} /></Box>;
}
