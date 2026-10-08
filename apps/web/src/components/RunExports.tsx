"use client";

import { useState } from "react";
import { Alert, Button } from "@mui/material";
import { downloadRunExport, exportLabels, type ExportKind } from "@/lib/api/exports";

export function RunExports({ id, selection }: { id: number; selection: boolean }) {
  const [busy, setBusy] = useState<ExportKind | null>(null);
  const [message, setMessage] = useState("");
  const [error, setError] = useState(false);
  async function download(kind: ExportKind) {
    setBusy(kind); setMessage(""); setError(false);
    try {
      const { blob, filename } = await downloadRunExport(id, kind);
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a"); link.href = url; link.download = filename;
      document.body.appendChild(link); link.click(); link.remove();
      window.setTimeout(() => URL.revokeObjectURL(url), 1000);
      setMessage(`Файл ${filename} передан браузеру для сохранения.`);
    } catch (caught) { setError(true); setMessage(caught instanceof Error ? caught.message : "Экспорт не выполнен."); }
    finally { setBusy(null); }
  }
  return <><div className="action-row" aria-label="Экспорт запуска" aria-busy={busy !== null}>
    {(Object.keys(exportLabels) as ExportKind[]).filter(kind => selection || kind !== "selected-features.csv").map(kind => <Button key={kind} variant="outlined" disabled={busy !== null} onClick={() => download(kind)}>{busy === kind ? "Готовим файл…" : exportLabels[kind]}</Button>)}
  </div>{message && <Alert severity={error ? "error" : "success"} role={error ? "alert" : "status"} sx={{ mt: 2 }}>{message}</Alert>}</>;
}
