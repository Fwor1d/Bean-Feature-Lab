import Link from "@/components/ClientLink";
import { Alert, Button, Chip } from "@mui/material";
import { IconArrowRight, IconDatabase, IconPlayerPlay } from "@tabler/icons-react";
import { api, apiErrorMessage } from "@/lib/api/client";
import { metric, modelLabel } from "@/lib/science";

export default async function HomePage() {
  let error: string | null = null;
  let datasets: Awaited<ReturnType<typeof api.datasets>> = [];
  let runs: Awaited<ReturnType<typeof api.runs>> = [];
  let experiments: Awaited<ReturnType<typeof api.experiments>> = [];
  let points: Awaited<ReturnType<typeof api.featureBudgetSeries>> = [];
  let sufficiency: Awaited<ReturnType<typeof api.coreSufficiency>> = [];
  try {
    [datasets, runs, experiments, points, sufficiency] = await Promise.all([api.datasets(), api.runs(), api.experiments(), api.featureBudgetSeries(), api.coreSufficiency()]);
  } catch (caught) { error = apiErrorMessage(caught); }
  const completed = runs.filter(run => run.status === "COMPLETED");
  const miPoints = points.filter(point => point.selector === "mutual_information" && point.budget_kind === "original_features");
  const fullProtocol = miPoints.length;
  const observedConditions = new Map<string, Set<number>>();
  for (const point of miPoints) {
    const key = `${point.model}:${point.dataset_hash}:${point.outer_split_set_sha256}`;
    const budgets = observedConditions.get(key) ?? new Set<number>();
    budgets.add(point.budget_value);
    observedConditions.set(key, budgets);
  }
  const partial = [...observedConditions.values()].some(budgets => budgets.size < 16);
  const latest = miPoints.find(point => runs.some(run => run.display_id === point.run_id));
  const latestRun = runs.find(run => run.display_id === latest?.run_id);
  const baseline = runs.find(run => {
    const config = experiments.find(item => item.id === run.experiment_id)?.configuration;
    return run.status === "COMPLETED" && config?.selector === "none" && config.k_original_features === 16;
  });
  const baselineConfig = experiments.find(item => item.id === baseline?.experiment_id)?.configuration;
  return <>
    <h1 className="page-heading">Состояние исследования</h1>
    <p className="page-question">Сколько исходных морфологических признаков нужно для классификации сортов фасоли без существенной потери Macro-F1 относительно модели на всех 16 измерениях?</p>
    {error && <Alert severity="warning" sx={{ mb: 2 }}>{error} <Link href="/">Повторить запрос</Link></Alert>}
    <section className="section-surface" aria-labelledby="overview-title">
      <h2 id="overview-title" className="section-title">Проверяемая цепочка · данные → условия → run</h2>
      <div className="status-line"><IconDatabase size={19} /><strong>Датасет</strong><span>{datasets[0]?.validated ? `UCI Dry Bean · ID ${datasets[0].source_id} · ${datasets[0].rows?.toLocaleString("ru-RU")} строк · ${datasets[0].feature_count} признаков` : "Не зарегистрирован"}</span><Chip label={datasets[0]?.validated ? "Проверен" : "Не загружен"} size="small" variant="outlined" color={datasets[0]?.validated ? "success" : "default"} /></div>
      <hr className="section-rule" />
      <div className="status-line"><IconPlayerPlay size={19} /><strong>Запуски</strong><span>{runs.length} в журнале · {completed.length} завершено · {runs.length - completed.length} в других состояниях</span><Button component={Link} href="/runs" size="small" endIcon={<IconArrowRight size={15} />}>Открыть журнал</Button></div>
      <hr className="section-rule" />
      <p className="table-note">{fullProtocol > 0 ? `Рассчитано условий Mutual Information: ${fullProtocol}. Полная кривая содержит 16 значений k для каждой модели; ${partial ? "текущий набор результатов частичный" : "наблюдаемые серии содержат все 16 значений k"}.` : "Рассчитанных full-protocol MI условий пока нет. График остаётся пустым."}</p>
      {latest && latestRun && <p><Link href={`/runs/${latestRun.id}`}>{latest.run_id}</Link> · {modelLabel[latest.model]} · MI · k={latest.budget_value} · Macro-F1 {metric(latest.macro_f1_mean)} · Accuracy {metric(latestRun.metrics?.accuracy_mean)}</p>}
      {baseline && baselineConfig && <p><Link href={`/runs/${baseline.id}`}>{baseline.display_id}</Link> · {modelLabel[baselineConfig.model]} · baseline на 16 исходных признаках · Macro-F1 {metric(baseline.metrics?.macro_f1_mean)}.</p>}
      <div className="action-row"><Button component={Link} href="/feature-budget" variant="contained" endIcon={<IconArrowRight size={17} />}>Исследовать Feature Budget</Button><Button component={Link} href="/features" variant="outlined">Проверить датасет и признаки</Button></div>
    </section>
    <p className="scientific-footnote">Минимальное sufficient k по заранее зафиксированному corrected repeated-CV методу: {sufficiency.length ? sufficiency.map(item => `${modelLabel[item.model]} — ${item.status !== "CALCULATED" ? "не рассчитано" : item.minimal_sufficient_k ?? "не установлено"}`).join(" · ") : "не рассчитано"}. Margin 0,01 и Bonferroni 0,05/15 заданы до расчёта; отсутствующие условия не достраиваются.</p>
  </>;
}
