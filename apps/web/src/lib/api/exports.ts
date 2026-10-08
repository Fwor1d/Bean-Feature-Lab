import { ApiError, apiErrorMessage } from "./client";

export const exportLabels = {
  "result.json": "Результат JSON", "config.json": "Снимок config", "summary.md": "Сводка Markdown",
  "folds.csv": "Folds CSV", "selected-features.csv": "Отбор признаков CSV",
} as const;
export type ExportKind = keyof typeof exportLabels;

export async function downloadRunExport(id: number, kind: ExportKind): Promise<{ blob: Blob; filename: string }> {
  let response: Response;
  try {
    response = await fetch(`/api/backend/api/v1/runs/${id}/export/${kind}`, { cache: "no-store", signal: AbortSignal.timeout(60_000) });
  } catch { throw new Error("Экспорт недоступен. Проверьте API и повторите запрос."); }
  if (!response.ok) {
    const body = await response.json().catch(() => null);
    throw new Error(apiErrorMessage(new ApiError(response.status, body?.error?.code ?? "export_failed", body?.error?.message ?? "Не удалось экспортировать run.")));
  }
  const expected = kind.endsWith("json") ? "application/json" : kind.endsWith("csv") ? "text/csv" : "text/markdown";
  if (response.headers.get("Content-Type")?.split(";")[0] !== expected) throw new Error("Получен некорректный формат экспорта. Повторите запрос.");
  const blob = await response.blob();
  if (blob.size > 32 * 1024 * 1024) throw new Error("Экспорт превышает допустимый размер 32 MiB.");
  return { blob, filename: `RUN-${String(id).padStart(6, "0")}-${kind}` };
}
