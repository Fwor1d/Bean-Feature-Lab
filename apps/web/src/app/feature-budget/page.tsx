import Link from "next/link";
import { Alert, Chip, Table, TableBody, TableCell, TableHead, TableRow } from "@mui/material";
import { BudgetResultsGrid, type BudgetRow } from "@/components/BudgetResultsGrid";
import { EmptyPlot } from "@/components/EmptyPlot";
import { ScientificPlot } from "@/components/ScientificPlot";
import { api, apiErrorMessage } from "@/lib/api/client";
import type { CoreSufficiency, Experiment, FeatureBudgetPoint, Run } from "@/lib/api/contracts";
import { budgetCohorts, metric, modelLabel, selectorLabel } from "@/lib/science";

type Query = { budget?: string; model?: string; selector?: string; cohort?: string };

export default async function FeatureBudgetPage({ searchParams }: { searchParams: Promise<Query> }) {
  const query = await searchParams;
  const pca = query.budget === "pca_components";
  let series: FeatureBudgetPoint[] = [];
  let runs: Run[] = [];
  let experiments: Experiment[] = [];
  let sufficiency: CoreSufficiency[] = [];
  let error: string | null = null;
  try {
    [series, runs, experiments, sufficiency] = await Promise.all([
      api.featureBudgetSeries(), api.runs(), api.experiments(), api.coreSufficiency(),
    ]);
  } catch (caught) { error = apiErrorMessage(caught); }

  const experimentById = new Map(experiments.map(item => [item.id, item]));
  const runByDisplayId = new Map(runs.map(item => [item.display_id, item]));
  const selectedModel = query.model ?? "all";
  const selectedSelector = pca ? "pca" : query.selector ?? "mutual_information";
  const selectedBudgetKind = pca ? "pca_components" : "original_features";
  const eligiblePoints = series.filter(point => point.budget_kind === selectedBudgetKind &&
    point.selector === selectedSelector && (selectedModel === "all" || point.model === selectedModel));
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
    model: point.model, condition: selectorLabel[point.selector], k: point.budget_value,
    macroF1: point.macro_f1_mean, accuracy: point.accuracy_mean,
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
    budgets.add(point.budget_value);
    perModel.set(point.model, budgets);
  }
  const expectedPoints = ["anova", "rfe", "tree_importance"].includes(selectedSelector) ? 6 : 16;
  const partial = points.length > 0 && [...perModel.values()].some(budgets => budgets.size < expectedPoints);
  const measured = [...perModel.entries()].map(([model, budgets]) => `${modelLabel[model as FeatureBudgetPoint["model"]]}: ${budgets.size}/${expectedPoints}`).join(" · ");
  const visibleModels = new Set(points.map(point => point.model));
  const visibleSufficiency = selectedSelector === "mutual_information" && !pca
    ? sufficiency.filter(item => visibleModels.has(item.model)) : [];
  const sufficientMarkers = visibleSufficiency.flatMap(item => item.minimal_sufficient_k == null
    ? [] : [{ model: item.model, k: item.minimal_sufficient_k }]);
  return <>
    <h1 className="page-heading">Бюджет признаков</h1>
    <p className="page-question">Как меняется Macro-F1 при сокращении числа исходных измеряемых признаков? Каждая точка — завершённое условие полного nested CV; отсутствующие k не интерполируются.</p>
    {error && <Alert severity="warning" sx={{ mb: 2 }}>{error} <Link href="/feature-budget">Повторить запрос</Link></Alert>}
    {pca && <Alert severity="info" sx={{ mb: 2 }}>PCA — отдельное представление: число компонент не равно числу физических измерений. Даже 1 component требует все 16 исходных измерений.</Alert>}
    {cohortEntries.length > 1 && <Alert severity="info" sx={{ mb: 2 }}>
      Разные версии данных или outer-разбиения не объединяются в одну кривую. Наборы: {cohortEntries.map(([key, values], index) => {
        const params = new URLSearchParams({ ...query, cohort: key });
        return <span key={key}>{index > 0 ? " · " : " "}<Link href={`/feature-budget?${params.toString()}`} aria-current={key === selectedCohort ? "true" : undefined}>Набор {index + 1} ({values.length} условий)</Link></span>;
      })}
    </Alert>}
    {partial && <Alert severity="info" sx={{ mb: 2 }}>Частичные результаты · {measured}. Линии между точками не строятся.</Alert>}
    {!error && points.length === 0 && <Alert severity="info" sx={{ mb: 2 }}>Для выбранного фильтра нет завершённых full-protocol условий. Smoke runs и queued/running conditions не входят в научную фигуру.</Alert>}
    <section className="figure-surface" aria-labelledby="figure-title">
      <div className="figure-heading"><h2 id="figure-title">Macro-F1 · {pca ? "PCA components" : "исходные признаки"} · {selectorLabel[selectedSelector as FeatureBudgetPoint["selector"]]}</h2>
        <Chip label={!points.length ? "Не рассчитано" : partial ? "Частичные результаты" : "Рассчитано"} size="small" variant="outlined" />
      </div>
      {!points.length ? <EmptyPlot pca={pca} /> : <ScientificPlot points={points} baselines={baselines.map(item => ({ runId: item.run.display_id, model: item.model, macroF1: item.macroF1 }))} sufficient={sufficientMarkers} />}
      <p className="table-note">{pca ? `Только реально завершённые PCA conditions; components не являются физическими признаками. Набор: ${selectedCohort ? `${selectedCohort.slice(0, 12)}…` : "не рассчитано"}.` : `Только сохранённые значения; ромб — сопоставимый baseline, зелёное кольцо — минимальное sufficient k только для Core MI. Контрольные comparator points не интерполируются. Набор: ${selectedCohort ? `${selectedCohort.slice(0, 12)}… · outer ${selectedCohort.slice(65, 77)}…` : "не рассчитано"}.`}</p>
    </section>
    <section className="table-surface" aria-labelledby="table-title">
      <div className="table-heading"><h2 id="table-title">Завершённые условия</h2><span className="table-note">{rows.length} записей · Accuracy из того же run</span></div>
      <BudgetResultsGrid rows={rows} budgetHeader={pca ? "PCA components" : "Исходных признаков"} />
    </section>
    {visibleSufficiency.length > 0 && <section className="table-surface" aria-labelledby="sufficiency-title">
      <div className="table-heading"><h2 id="sufficiency-title">Paired sufficient-k analysis</h2><span className="table-note">Corrected one-sided upper bound · margin 0,01</span></div>
      <Table size="small" aria-label="Результаты sufficient-k по моделям"><TableHead><TableRow><TableCell>Модель</TableCell><TableCell align="right">Минимальное k</TableCell><TableCell align="right">Средняя потеря</TableCell><TableCell align="right">Upper bound</TableCell><TableCell>Baseline</TableCell></TableRow></TableHead><TableBody>{visibleSufficiency.map(item => {
        const comparison = item.comparisons.find(value => value.k_original_features === item.minimal_sufficient_k);
        return <TableRow key={item.model}><TableCell>{modelLabel[item.model]}</TableCell><TableCell align="right">{item.minimal_sufficient_k ?? "не установлено"}</TableCell><TableCell align="right">{metric(comparison?.mean_loss ?? null, 5)}</TableCell><TableCell align="right">{metric(comparison?.one_sided_upper_confidence_bound ?? null, 5)}</TableCell><TableCell>{item.baseline_run_id ? <Link href={`/runs/${Number(item.baseline_run_id.slice(4))}`}>{item.baseline_run_id}</Link> : "—"}</TableCell></TableRow>;
      })}</TableBody></Table>
    </section>}
    <p className="scientific-footnote">Критерий: paired loss относительно baseline той же модели, margin 0,01; one-sided Nadeau–Bengio corrected interval с Bonferroni 0,05/15. {visibleSufficiency.length ? visibleSufficiency.map(item => `${modelLabel[item.model]}: ${item.status === "CALCULATED" ? item.minimal_sufficient_k ?? "не установлено" : item.status === "PARTIAL" ? `частично (${item.calculated_comparisons}/15)` : "не рассчитано"}`).join(" · ") : "Для выбранных моделей решений нет."}</p>
  </>;
}
