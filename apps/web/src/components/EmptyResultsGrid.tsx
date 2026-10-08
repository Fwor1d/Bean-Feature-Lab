"use client";

import { Box, Typography, useMediaQuery } from "@mui/material";
import { ruRU } from "@mui/x-data-grid/locales";
import { DataGrid, type GridColDef } from "@mui/x-data-grid";

const originalColumns: GridColDef[] = [
  { field: "feature", headerName: "Исходный признак", flex: 1, minWidth: 190 },
  { field: "model", headerName: "Модель", width: 150 },
  { field: "selector", headerName: "Метод", width: 160 },
  { field: "frequency", headerName: "Частота отбора", width: 155 },
  { field: "status", headerName: "Статус", width: 150 },
];

const pcaColumns: GridColDef[] = [
  { field: "component", headerName: "Компонента PCA", flex: 1, minWidth: 190 },
  { field: "model", headerName: "Модель", width: 160 },
  { field: "source", headerName: "Исходных измерений", width: 185 },
  { field: "status", headerName: "Статус", width: 150 },
];

function NoRows({ pca }: { pca: boolean }) {
  return <Box sx={{ height: "100%", display: "grid", placeContent: "center", textAlign: "center", px: 2 }}>
    <Typography color="text.secondary" sx={{ fontWeight: 600 }}>{pca ? "Компоненты не рассчитаны" : "Признаки не рассчитаны"}</Typography>
    <Typography color="text.secondary" sx={{ fontSize: 13 }}>Таблица появится после настоящего эксперимента.</Typography>
  </Box>;
}

export function EmptyResultsGrid({ pca = false }: { pca?: boolean }) {
  const narrow = useMediaQuery("(max-width: 820px)");
  const columns = pca ? pcaColumns : originalColumns;
  return <Box sx={{ height: 160, width: "100%" }}>
    <DataGrid localeText={ruRU.components.MuiDataGrid.defaultProps.localeText} columns={narrow ? columns.filter(column => ["feature", "component", "status"].includes(column.field)) : columns} rows={[]} slots={{ noRowsOverlay: () => <NoRows pca={pca} /> }}
      initialState={{ pagination: { paginationModel: { pageSize: 10 } } }} pageSizeOptions={[10, 25, 50, 100]}
      hideFooter disableRowSelectionOnClick sx={{ fontSize: 13, "& .MuiDataGrid-columnHeaderTitle": { fontWeight: 600 } }} />
  </Box>;
}
