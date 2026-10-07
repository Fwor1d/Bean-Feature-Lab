import Link from "next/link";
import { Alert, Button, Chip, Stack, Table, TableBody, TableCell, TableHead, TableRow } from "@mui/material";
import { ComparisonSelector, type ComparisonOption } from "@/components/ComparisonSelector";
import { DescriptiveComparisonSelector, type DescriptiveRunOption } from "@/components/DescriptiveComparisonSelector";
import { api, apiErrorMessage } from "@/lib/api/client";
import type { DescriptiveComparison, PairedComparison, Run, RunSummary } from "@/lib/api/contracts";
import { metric, modelLabel, selectorLabel } from "@/lib/science";

interface CompareParams {
  view?: string;
  compact?: string;
  baseline?: string;
  left?: string;
  right?: string;
}

export default async function ComparePage({ searchParams }: { searchParams: Promise<CompareParams> }) {
  const params = await searchParams;
  if (params.view === "descriptive") return <DescriptiveView params={params} />;
  return <SufficiencyView params={params} />;
}

function CompareNavigation({ active }: { active: "sufficiency" | "descriptive" }) {
  return <Stack direction="row" spacing={1} sx={{ mb: 2 }}>
    <Button component={Link} href="/compare" variant={active === "sufficiency" ? "contained" : "outlined"}>Compact vs baseline</Button>
    <Button component={Link} href="/compare?view=descriptive" variant={active === "descriptive" ? "contained" : "outlined"}>Два условия</Button>
  </Stack>;
}

async function DescriptiveView({ params }: { params: CompareParams }) {
  let error: string | null = null;
  let result: DescriptiveComparison | null = null;
  let options: DescriptiveRunOption[] = [];
  let selected: { left: number; right: number } | null = null;
  try {
    const [runs, experiments] = await Promise.all([api.runs(), api.experiments()]);
    const configs = new Map(experiments.map(item => [item.id, item.configuration]));
    options = runs.flatMap(run => {
      const configuration = configs.get(run.experiment_id);
      if (run.status !== "COMPLETED" || !configuration || configuration.evaluation_mode === "smoke") return [];
      return [{ id: run.id, displayId: run.display_id, configuration }];
    });
    const requestedLeft = options.find(option => option.id === Number(params.left));
    const requestedRight = options.find(option => option.id === Number(params.right));
    const left = requestedLeft ?? options[0];
    const right = requestedRight && requestedRight.id !== left?.id
      ? requestedRight
      : options.find(option => option.id !== left?.id);
    if (left && right) {
      selected = { left: left.id, right: right.id };
      result = await api.descriptiveComparison(left.id, right.id);
    }
  } catch (caught) { error = apiErrorMessage(caught); }
  return <>
    <h1 className="page-heading">Сравнение условий</h1>
    <p className="page-question">Два завершённых условия сопоставляются по идентичным frozen outer folds. Разности описательные: экран не объявляет победителя и не подменяет заранее зафиксированный sufficient-k анализ.</p>
    <CompareNavigation active="descriptive" />
    {error && <Alert severity="warning" sx={{ mb: 2 }}>{error}</Alert>}
    {result && selected ? <>
      <DescriptiveComparisonSelector options={options} selected={selected} />
      {result.left_summary.budget_kind !== result.right_summary.budget_kind && <Alert severity="info" sx={{ mb: 2 }}>Представления различаются. PCA components и исходные физические признаки показаны раздельно и не трактуются как один budget.</Alert>}
      <section className="section-surface" aria-labelledby="descriptive-summary-title">
        <h2 id="descriptive-summary-title" className="section-title">Описательная парная разность A − B</h2>
        <div className="status-line" style={{ marginBottom: 16 }}><Chip label="Outer splits совпадают" color="success" size="small" variant="outlined" /><Chip label="Без inferential decision" size="small" variant="outlined" /><span>Dataset SHA-256 <code>{result.dataset_hash}</code></span></div>
        <dl className="metric-list">
          <div><dt>Условие A</dt><dd><Link href={`/runs/${selected.left}`}>{result.left_run_id}</Link> · {modelLabel[result.left_summary.model]} · {selectorLabel[result.left_summary.selector]} · Macro-F1 {metric(result.left_summary.macro_f1_mean)}</dd></div>
          <div><dt>Условие B</dt><dd><Link href={`/runs/${selected.right}`}>{result.right_run_id}</Link> · {modelLabel[result.right_summary.model]} · {selectorLabel[result.right_summary.selector]} · Macro-F1 {metric(result.right_summary.macro_f1_mean)}</dd></div>
          <div><dt>Средняя Δ Macro-F1</dt><dd>{metric(result.comparison.mean_macro_f1_difference_left_minus_right, 5)}</dd></div>
          <div><dt>Средняя Δ Accuracy</dt><dd>{metric(result.comparison.mean_accuracy_difference_left_minus_right, 5)}</dd></div>
          <div><dt>Nested search A / B</dt><dd>{result.left_resources.total_nested_search_seconds.toFixed(1)} / {result.right_resources.total_nested_search_seconds.toFixed(1)} s</dd></div>
          <div><dt>Размер pipeline A / B</dt><dd>{metric(result.left_resources.serialized_pipeline_bytes?.median, 0)} / {metric(result.right_resources.serialized_pipeline_bytes?.median, 0)} bytes</dd></div>
        </dl>
        <p className="table-note">{result.comparison.note} Положительная разность означает большее значение у условия A только в этой описательной paired-CV сводке.</p>
      </section>
      <section className="table-surface" aria-labelledby="descriptive-folds-title"><div className="table-heading"><h2 id="descriptive-folds-title">Разности по outer folds</h2><span className="table-note">{result.comparison.n_paired_folds} проверенных пар</span></div><Table size="small"><TableHead><TableRow><TableCell>Repeat / fold</TableCell><TableCell align="right">Δ Macro-F1</TableCell><TableCell align="right">Δ Accuracy</TableCell></TableRow></TableHead><TableBody>{result.comparison.fold_differences.map(item => <TableRow key={item.fold_id}><TableCell>{item.fold_id}</TableCell><TableCell align="right">{metric(item.macro_f1_difference_left_minus_right, 5)}</TableCell><TableCell align="right">{metric(item.accuracy_difference_left_minus_right, 5)}</TableCell></TableRow>)}</TableBody></Table></section>
    </> : !error && <section className="section-surface"><h2 className="section-title">Недостаточно условий</h2><p>Для сравнения нужны два завершённых full-protocol run на одинаковом dataset и frozen outer splits.</p></section>}
  </>;
}

async function SufficiencyView({ params }: { params: CompareParams }) {
  let error: string | null = null;
  let comparison: PairedComparison | null = null;
  let compact: Run | null = null;
  let baseline: Run | null = null;
  let compactSummary: RunSummary | null = null;
  let baselineSummary: RunSummary | null = null;
  let pairOptions: { compact: Run; baseline: Run }[] = [];
  let selectorOptions: ComparisonOption[] = [];
  try {
    const [runs, experiments] = await Promise.all([api.runs(), api.experiments()]);
    const configs = new Map(experiments.map(item => [item.id, item.configuration]));
    const fullRuns = runs.filter(run => run.status === "COMPLETED" && configs.get(run.experiment_id)?.evaluation_mode !== "smoke");
    const pairs = fullRuns.flatMap(candidate => {
      const condition = configs.get(candidate.experiment_id);
      if (!condition || condition.budget_kind !== "original_features" || condition.selector !== "mutual_information" || !condition.k_original_features || condition.k_original_features >= 16) return [];
      return fullRuns.filter(other => {
        const reference = configs.get(other.experiment_id);
        return reference?.selector === "none" && reference.model === condition.model && reference.k_original_features === 16 && reference.dataset_version === condition.dataset_version && reference.seed === condition.seed;
      }).map(other => ({ compact: candidate, baseline: other }));
    });
    pairOptions = pairs;
    selectorOptions = pairs.flatMap(pair => {
      const configuration = configs.get(pair.compact.experiment_id);
      return configuration?.k_original_features ? [{ compactId: pair.compact.id, baselineId: pair.baseline.id, compactDisplayId: pair.compact.display_id, baselineDisplayId: pair.baseline.display_id, model: configuration.model, k: configuration.k_original_features }] : [];
    }).sort((a, b) => a.model.localeCompare(b.model) || a.k - b.k);
    const selected = pairs.find(pair => pair.compact.id === Number(params.compact) && pair.baseline.id === Number(params.baseline)) ?? pairs[0];
    if (selected) {
      compact = selected.compact; baseline = selected.baseline;
      [comparison, compactSummary, baselineSummary] = await Promise.all([api.pairedComparison(compact.id, baseline.id), api.runSummary(compact.id), api.runSummary(baseline.id)]);
    }
  } catch (caught) { error = apiErrorMessage(caught); }
  const sameSplits = compactSummary?.summary?.outer_split_set_sha256 === baselineSummary?.summary?.outer_split_set_sha256 && !!compactSummary?.summary;
  return <>
    <h1 className="page-heading">Парное сравнение</h1>
    <p className="page-question">Компактная MI-конфигурация сопоставляется с baseline той же модели на тех же outer folds. Решение использует заранее зафиксированный corrected repeated-CV interval и margin 0,01.</p>
    <CompareNavigation active="sufficiency" />
    {error && <Alert severity="warning" sx={{ mb: 2 }}>{error}</Alert>}
    {comparison && compact && baseline ? <>
      {selectorOptions.length > 1 && <ComparisonSelector options={selectorOptions} selected={{ compactId: compact.id, baselineId: baseline.id }} />}
      <section className="section-surface" aria-labelledby="comparison-title">
        <h2 id="comparison-title" className="section-title">{modelLabel[compactSummary!.summary!.model]} · исходные признаки</h2>
        <div className="status-line" style={{ marginBottom: 16 }}><Chip label={sameSplits ? "Outer splits совпадают" : "Разбиения не совпали"} color={sameSplits ? "success" : "error"} size="small" variant="outlined" /><span>Dataset SHA-256 <code>{comparison.dataset_hash}</code></span></div>
        <div className="status-line" style={{ marginBottom: 16 }}><Chip label={comparison.comparison.decision === "sufficient" ? "Sufficient" : "Not sufficient"} color={comparison.comparison.decision === "sufficient" ? "success" : "warning"} size="small" /><span>one-sided UCB {metric(comparison.comparison.one_sided_upper_confidence_bound, 5)}</span></div>
        <dl className="metric-list"><div><dt>Компактный run</dt><dd><Link href={`/runs/${compact.id}`}>{compact.display_id}</Link> · k={compactSummary?.summary?.k_original_features} · {metric(compact.metrics?.macro_f1_mean)}</dd></div><div><dt>Baseline</dt><dd><Link href={`/runs/${baseline.id}`}>{baseline.display_id}</Link> · 16 признаков · {metric(baseline.metrics?.macro_f1_mean)}</dd></div><div><dt>Средняя парная потеря</dt><dd>{metric(comparison.comparison.mean_loss)}</dd></div><div><dt>Corrected SE</dt><dd>{metric(comparison.comparison.corrected_standard_error, 5)}</dd></div><div><dt>Margin Macro-F1</dt><dd>{metric(comparison.comparison.margin_macro_f1, 2)}</dd></div><div><dt>Достаточное k</dt><dd>{comparison.comparison.decision === "sufficient" ? comparison.comparison.sufficient_k : "нет"}</dd></div></dl>
        <p className="table-note">Потеря = Macro-F1 baseline − Macro-F1 compact на одном outer fold. {comparison.comparison.interval_method}; one-sided α={comparison.comparison.comparison_alpha.toFixed(5)}, Bonferroni within-model 15 comparisons. Repeated-CV dependence учтена поправкой, naive SE не используется.</p>
      </section>
      <section className="table-surface" aria-labelledby="paired-title"><div className="table-heading"><h2 id="paired-title">Парные различия по folds</h2><span className="table-note">{comparison.comparison.paired_losses.length} проверенных пар · {pairOptions.length} доступных пар runs</span></div><Table size="small" aria-label="Парные потери Macro-F1"><TableHead><TableRow><TableCell>Repeat / fold</TableCell><TableCell align="right">Потеря Macro-F1</TableCell></TableRow></TableHead><TableBody>{comparison.comparison.paired_losses.map(item => <TableRow key={item.fold_id}><TableCell>{item.fold_id}</TableCell><TableCell align="right">{metric(item.loss_macro_f1, 5)}</TableCell></TableRow>)}</TableBody></Table></section>
    </> : !error && <section className="section-surface"><h2 className="section-title">Нет сопоставимой пары</h2><p>Требуются завершённые full-protocol MI run с k &lt; 16 и baseline той же модели на 16 исходных признаках с одинаковыми данными и разбиениями.</p><Link href="/runs">Открыть журнал запусков</Link></section>}
  </>;
}
