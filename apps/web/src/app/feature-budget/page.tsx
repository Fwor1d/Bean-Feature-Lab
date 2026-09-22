import Link from "next/link";
import { Alert, Chip } from "@mui/material";
import { BudgetResultsGrid, type BudgetRow } from "@/components/BudgetResultsGrid";
import { EmptyPlot } from "@/components/EmptyPlot";
import { ScientificPlot } from "@/components/ScientificPlot";
import { api, apiErrorMessage } from "@/lib/api/client";
import type { Experiment, FeatureBudgetPoint, Run } from "@/lib/api/contracts";
import { budgetCohorts, metric, modelLabel } from "@/lib/science";

type Query = { budget?: string; model?: string; selector?: string; cohort?: string };

export default async function FeatureBudgetPage({ searchParams }: { searchParams: Promise<Query> }) {
  const query = await searchParams;
  const pca = query.budget === "pca_components";
  let series: FeatureBudgetPoint[] = [];
  let runs: Run[] = [];
  let experiments: Experiment[] = [];
  let error: string | null = null;
  try {
    [series, runs, experiments] = await Promise.all([api.featureBudgetSeries(), api.runs(), api.experiments()]);
  } catch (caught) { error = apiErrorMessage(caught); }

  const experimentById = new Map(experiments.map(item => [item.id, item]));
  const runByDisplayId = new Map(runs.map(item => [item.display_id, item]));
  const selectedModel = query.model ?? "all";
  const selectedSelector = query.selector ?? "mutual_information";
  const eligiblePoints = pca || selectedSelector !== "mutual_information" ? [] : series.filter(point =>
    point.budget_kind === "original_features" && (selectedModel === "all" || point.model === selectedModel)
  );
  // A curve may contain only conditions evaluated on the same data and frozen outer splits.
  const cohortEntries = budgetCohorts(eligiblePoints);
  const cohorts = new Map(cohortEntries);
  const selectedCohort = cohorts.has(query.cohort ?? "") ? query.cohort! : cohortEntries[0]?.[0];
  const points = selectedCohort ? cohorts.get(selectedCohort) ?? [] : [];
  const baselineCandidates = pca ? [] : runs.filter(run => {
    const config = experimentById.get(run.experiment_id)?.configuration;
    return run.status === "COMPLETED" && run.metrics && config?.selector === "none" &&
      config.budget_kind === "original_features" && config.k_original_features === 16 &&
      (selectedModel === "all" || config.model === selectedModel);
  });
  const baselineChecks = await Promise.all(baselineCandidates.map(async run => {
    try {
      const [summary, detail] = await Promise.all([api.runSummary(run.id), api.runDetail(run.id)]);
      const compatible = points.some(point => point.model === summary.summary?.model &&
        point.dataset_hash === detail.dataset_manifest.arff_sha256 &&
        point.outer_split_set_sha256 === summary.summary?.outer_split_set_sha256);
      return compatible && run.metrics ? {
        run, summary, model: modelLabel[summary.summary!.model], macroF1: run.metrics.macro_f1_mean,
      } : null;
    } catch { return null; }
  }));
  const baselines = baselineChecks.filter((item): item is NonNullable<typeof item> => item !== null);
  const rows: BudgetRow[] = points.map(point => ({
    id: point.run_id, runId: runByDisplayId.get(point.run_id)?.id ?? Number(point.run_id.slice(4)),
    model: point.model, condition: "Mutual Information", k: point.k_original_features,
    macroF1: point.macro_f1_mean, accuracy: runByDisplayId.get(point.run_id)?.metrics?.accuracy_mean ?? null,
  }));
  rows.push(...baselines.map(item => ({
    id: item.run.display_id, runId: item.run.id, model: item.summary.summary!.model,
    condition: "Baseline · без отбора", k: 16,
    macroF1: item.macroF1, accuracy: item.run.metrics?.accuracy_mean ?? null,
  })));
  rows.sort((a, b) => a.model.localeCompare(b.model) || a.k - b.k || a.condition.localeCompare(b.condition));
  const perModel = new Map<string, Set<number>>();
  for (const point of points) {
    const budgets = perModel.get(point.model) ?? new Set<number>();
    budgets.add(point.k_original_features);
    perModel.set(point.model, budgets);
  }
  const partial = !pca && points.length > 0 && [...perModel.values()].some(budgets => budgets.size < 16);
  const measured = [...perModel.entries()].map(([model, budgets]) => `${modelLabel[model as FeatureBudgetPoint["model"]]}: ${budgets.size}/16`).join(" · ");
  const exampleRun = points[0] && runByDisplayId.get(points[0].run_id);
  const exampleSummary = exampleRun ? await api.runSummary(exampleRun.id).catch(() => null) : null;
  return <>
    <h1 className="page-heading">Бюджет признаков</h1>
    <p className="page-question">Как меняется Macro-F1 при сокращении числа исходных измеряемых признаков? Каждая точка — завершённое условие полного nested CV; отсутствующие k не интерполируются.</p>
    {error && <Alert severity="warning" sx={{ mb: 2 }}>{error} <Link href="/feature-budget">Повторить запрос</Link></Alert>}
    {pca && <Alert severity="info" sx={{ mb: 2 }}>PCA — отдельное представление: число компонент не равно числу физических измерений. Рассчитанных PCA runs для этой фигуры пока нет.</Alert>}
    {cohortEntries.length > 1 && <Alert severity="info" sx={{ mb: 2 }}>
      Разные версии данных или outer-разбиения не объединяются в одну кривую. Наборы: {cohortEntries.map(([key, values], index) => {
        const params = new URLSearchParams({ ...query, cohort: key });
        return <span key={key}>{index > 0 ? " · " : " "}<Link href={`/feature-budget?${params.toString()}`} aria-current={key === selectedCohort ? "true" : undefined}>Набор {index + 1} ({values.length} условий)</Link></span>;
      })}
    </Alert>}
    {partial && <Alert severity="info" sx={{ mb: 2 }}>Частичные результаты · {measured}. Линии между точками не строятся.</Alert>}
    {!error && !pca && points.length === 0 && <Alert severity="info" sx={{ mb: 2 }}>Для выбранного фильтра нет завершённых full-protocol условий. Smoke runs не входят в научную кривую.</Alert>}
    <section className="figure-surface" aria-labelledby="figure-title">
      <div className="figure-heading"><h2 id="figure-title">Macro-F1 · исходные признаки</h2>
        <Chip label={pca || !points.length ? "Не рассчитано" : partial ? "Частичные результаты" : "Рассчитано"} size="small" variant="outlined" />
      </div>
      {pca ? <EmptyPlot pca /> : <ScientificPlot points={points} baselines={baselines.map(item => ({ runId: item.run.display_id, model: item.model, macroF1: item.macroF1 }))} />}
      <p className="table-note">{pca ? "PCA требует все 16 исходных измерений." : `Только сохранённые значения; ромб — сопоставимый baseline на 16 исходных признаках. Набор: ${selectedCohort ? `${selectedCohort.slice(0, 12)}… · outer ${selectedCohort.slice(65, 77)}…` : "не рассчитано"}. Без статистического интервала достаточность k не определена.`}</p>
    </section>
    <section className="table-surface" aria-labelledby="table-title">
      <div className="table-heading"><h2 id="table-title">Завершённые условия</h2><span className="table-note">{rows.length} записей · Accuracy из того же run</span></div>
      <BudgetResultsGrid rows={pca ? [] : rows} />
    </section>
    <p className="scientific-footnote">Критерий достаточности: {metric(exampleSummary?.summary?.sufficient_k)}. Заранее заданная допустимая потеря — 0,01 Macro-F1 относительно baseline той же модели; метод интервала для зависимых folds ещё не утверждён.</p>
  </>;
}
