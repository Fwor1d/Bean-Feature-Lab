"use client";

import Link from "next/link";
import { Box } from "@mui/material";
import { ruRU } from "@mui/x-data-grid/locales";
import { DataGrid, type GridColDef } from "@mui/x-data-grid";
import { metric, modelLabel } from "@/lib/science";
import type { ModelId } from "@/lib/api/contracts";

export interface BudgetRow {
  id: string;
  runId: number;
  model: ModelId;
  condition: string;
  k: number;
  macroF1: number;
  accuracy: number | null;
}

const columns: GridColDef<BudgetRow>[] = [
  { field: "id", headerName: "Run ID", width: 124, renderCell: ({ row }) => <Link href={`/runs/${row.runId}`}>{row.id}</Link> },
  { field: "k", headerName: "Исходных признаков", width: 132, type: "number" },
  { field: "macroF1", headerName: "Macro-F1", width: 101, type: "number", valueFormatter: value => metric(value) },
  { field: "accuracy", headerName: "Accuracy", width: 98, type: "number", valueFormatter: value => metric(value) },
  { field: "model", headerName: "Модель", minWidth: 170, flex: 1, valueFormatter: value => modelLabel[value as ModelId] },
  { field: "condition", headerName: "Условие", minWidth: 185, flex: 1 },
];

export function BudgetResultsGrid({ rows, budgetHeader = "Исходных признаков" }: { rows: BudgetRow[]; budgetHeader?: string }) {
  const visibleColumns = columns.map(column => column.field === "k" ? { ...column, headerName: budgetHeader } : column);
  return <Box sx={{ width: "100%", minHeight: 170 }}><p className="grid-scroll-note">Для остальных колонок прокрутите таблицу вправо →</p>
    <DataGrid rows={rows} columns={visibleColumns} density="compact" disableRowSelectionOnClick
      initialState={{ pagination: { paginationModel: { pageSize: 10 } } }} pageSizeOptions={[10, 25, 50]}
      localeText={{ ...ruRU.components.MuiDataGrid.defaultProps.localeText, noRowsLabel: "Нет рассчитанных условий для этого представления" }}
      sx={{ border: 0, "& .MuiDataGrid-cell": { fontVariantNumeric: "tabular-nums" } }} />
  </Box>;
}
