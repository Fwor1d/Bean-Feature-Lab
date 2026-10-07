import { Alert } from "@mui/material";
import { RunsGrid, type RunGridRow } from "@/components/RunsGrid";
import { api, apiErrorMessage } from "@/lib/api/client";
import { modelLabel, selectorLabel } from "@/lib/science";

export default async function RunsPage() {
  let rows: RunGridRow[] = [];
  let error: string | null = null;
  try {
    const [runs, experiments] = await Promise.all([api.runs(), api.experiments()]);
    const configurations = new Map(experiments.map(item => [item.id, item.configuration]));
    const summaries = await Promise.all(runs.map(run => run.status === "COMPLETED" ? api.runSummary(run.id).catch(() => null) : null));
    rows = runs.map((run, index) => {
      const config = configurations.get(run.experiment_id);
      return {
        id: run.id, displayId: run.display_id,
        model: config ? modelLabel[config.model] : `Конфигурация #${run.experiment_id}`,
        selector: config ? selectorLabel[config.selector] : "—",
        budget: config?.budget_kind === "pca_components" ? `${config.n_components} компонент PCA` : config?.budget_kind === "sparse_original_features" ? `L1 C=${String(config.selector_configuration?.C)} · variable` : config ? `${config.k_original_features} исходных` : "—",
        status: run.status, macroF1: run.metrics?.macro_f1_mean ?? null,
        accuracy: run.metrics?.accuracy_mean ?? null,
        folds: summaries[index]?.summary?.outer_fold_count ?? null,
        created: run.created_at, finished: run.finished_at,
      };
    });
  } catch (caught) { error = apiErrorMessage(caught); }
  const running = rows.filter(row => row.status === "RUNNING" || row.status === "QUEUED").length;
  return <>
    <h1 className="page-heading">Запуски</h1>
    <p className="page-question">Журнал реальных исполнений. Статус запуска и наличие научных метрик показаны отдельно; откройте Run ID для folds и происхождения результата.</p>
    {error && <Alert severity="warning" sx={{ mb: 2 }}>{error}</Alert>}
    {running > 0 && <Alert severity="info" sx={{ mb: 2 }} role="status">В очереди или выполняется: {running}. Результат появится после завершения всех outer folds. Обновите страницу для нового состояния.</Alert>}
    <section className="table-surface" aria-labelledby="runs-title">
      <div className="table-heading"><h2 id="runs-title">Очередь и история</h2><span className="table-note">{rows.length} запусков · только сохранённые метрики</span></div>
      {!error && rows.length === 0 && <p className="empty-copy">Запусков пока нет. Сохраните конфигурацию в разделе «Эксперименты» и поставьте её в очередь.</p>}
      {rows.length > 0 && <RunsGrid rows={rows} />}
    </section>
  </>;
}
