import Link from "next/link";
import { Alert, Chip, Table, TableBody, TableCell, TableHead, TableRow } from "@mui/material";
import { ComparisonSelector, type ComparisonOption } from "@/components/ComparisonSelector";
import { api, apiErrorMessage } from "@/lib/api/client";
import type { PairedComparison, Run, RunSummary } from "@/lib/api/contracts";
import { metric, modelLabel } from "@/lib/science";

export default async function ComparePage({ searchParams }: { searchParams: Promise<{ compact?: string; baseline?: string }> }) {
  const params = await searchParams;
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
      return configuration?.k_original_features ? [{
        compactId: pair.compact.id, baselineId: pair.baseline.id,
        compactDisplayId: pair.compact.display_id, baselineDisplayId: pair.baseline.display_id,
        model: configuration.model, k: configuration.k_original_features,
      }] : [];
    }).sort((a, b) => a.model.localeCompare(b.model) || a.k - b.k);
    const selected = pairs.find(pair => pair.compact.id === Number(params.compact) && pair.baseline.id === Number(params.baseline)) ?? pairs[0];
    if (selected) {
      compact = selected.compact; baseline = selected.baseline;
      [comparison, compactSummary, baselineSummary] = await Promise.all([
        api.pairedComparison(compact.id, baseline.id), api.runSummary(compact.id), api.runSummary(baseline.id),
      ]);
    }
  } catch (caught) { error = apiErrorMessage(caught); }
  const sameSplits = compactSummary?.summary?.outer_split_set_sha256 === baselineSummary?.summary?.outer_split_set_sha256 && !!compactSummary?.summary;
  return <>
    <h1 className="page-heading">Парное сравнение</h1>
    <p className="page-question">Компактная MI-конфигурация сопоставляется с baseline той же модели на тех же outer folds. Решение использует заранее зафиксированный corrected repeated-CV interval и margin 0,01.</p>
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
