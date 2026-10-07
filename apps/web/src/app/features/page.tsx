import Link from "next/link";
import { Alert, Chip, Table, TableBody, TableCell, TableHead, TableRow } from "@mui/material";
import { FeatureExplorerControls } from "@/components/FeatureExplorerControls";
import { FeatureSelectionHeatmap } from "@/components/FeatureSelectionHeatmap";
import { api, apiErrorMessage } from "@/lib/api/client";
import type { DatasetManifest, DatasetQuality, FeatureSelectionPoint, ModelId, SelectorId } from "@/lib/api/contracts";
import { metric, modelLabel, selectorLabel } from "@/lib/science";

type Query = { model?: string; selector?: string; k?: string };

export default async function FeaturesPage({ searchParams }: { searchParams: Promise<Query> }) {
  const query = await searchParams;
  let manifest: DatasetManifest | null = null;
  let quality: DatasetQuality | null = null;
  let selectionSeries: FeatureSelectionPoint[] = [];
  let error: string | null = null;
  try {
    const [datasets, selection] = await Promise.all([api.datasets(), api.featureSelectionSeries()]);
    selectionSeries = selection;
    if (datasets[0]) [manifest, quality] = await Promise.all([
      api.datasetManifest(datasets[0].id), api.datasetQuality(datasets[0].id),
    ]);
  } catch (caught) { error = apiErrorMessage(caught); }
  const validSeries = manifest ? selectionSeries.filter(point => point.dataset_hash === manifest!.arff_sha256) : [];
  const requested = validSeries.find(point => point.model === query.model && point.selector === query.selector && point.k_original_features === Number(query.k));
  const preferred = validSeries.find(point => point.model === "logistic_regression" && point.selector === "mutual_information" && point.k_original_features === 14);
  const modelFallback = validSeries.filter(point => !query.model || point.model === query.model).filter(point => !query.selector || point.selector === query.selector).sort((a, b) => b.k_original_features - a.k_original_features)[0];
  const selected = requested ?? (query.model || query.selector ? modelFallback : preferred) ?? modelFallback ?? validSeries[0] ?? null;
  const frequency = selected?.selection_frequency;
  const sourceRunId = selected ? Number(selected.run_id.slice(4)) : null;
  const models = [...new Set(validSeries.map(point => point.model))].sort() as ModelId[];
  const selectors = [...new Set(validSeries.filter(point => !selected || point.model === selected.model).map(point => point.selector))].sort() as SelectorId[];
  const heatmapPoints = selected ? validSeries.filter(point => point.model === selected.model && point.selector === selected.selector && point.outer_split_set_sha256 === selected.outer_split_set_sha256) : [];
  const budgets = heatmapPoints.map(point => point.k_original_features).sort((a, b) => a - b);
  const expectedBudgets = selected && ["anova", "rfe", "tree_importance"].includes(selected.selector) ? 6 : 16;
  const firstSelectedBudget = new Map((manifest?.features ?? []).map(feature => [feature,
    heatmapPoints.filter(point => (point.selection_frequency[feature] ?? 0) > 0)
      .map(point => point.k_original_features).sort((a, b) => a - b)[0] ?? null]));
  return <>
    <h1 className="page-heading">Датасет и признаки</h1>
    <p className="page-question">Проверенный официальный ARFF UCI 602. Канонические имена сохранены; частоты отбора ниже относятся только к конкретному завершённому run.</p>
    {error && <Alert severity="warning" sx={{ mb: 2 }}>{error}</Alert>}
    {manifest ? <>
      <section className="section-surface" aria-labelledby="dataset-title">
        <h2 id="dataset-title" className="section-title">{manifest.source} · ID {manifest.source_id}</h2>
        <div className="status-line"><Chip label="Валидация пройдена" color="success" size="small" variant="outlined" /><span>{manifest.rows.toLocaleString("ru-RU")} объектов · {manifest.feature_count} численных признаков · {manifest.classes.length} классов · {manifest.missing_values} пропусков</span></div>
        <p className="table-note">Целевой столбец: {manifest.target}. Классы: {manifest.classes.join(", ")}.</p>
        <dl className="detail-list"><div><dt>Источник</dt><dd><a href={manifest.source_url} target="_blank" rel="noreferrer">Официальный UCI 602</a> · получен {new Date(manifest.retrieved_at_utc).toLocaleString("ru-RU", { timeZone: "UTC" })} UTC</dd></div>
          <div><dt>Dataset version</dt><dd><code>{manifest.dataset_version}</code></dd></div>
          <div><dt>ARFF SHA-256</dt><dd><code>{manifest.arff_sha256}</code></dd></div>
          <div><dt>ZIP SHA-256</dt><dd><code>{manifest.archive_sha256}</code></dd></div></dl>
        <Alert severity="info" sx={{ mt: 2 }}>{manifest.schema_notice}</Alert>
      </section>
      {quality && <section className="section-surface" aria-labelledby="quality-title">
        <h2 id="quality-title" className="section-title">Качество исходных данных</h2>
        <dl className="detail-list">
          <div><dt>Пропуски / Inf</dt><dd>{quality.missing_values} / {quality.infinite_values}</dd></div>
          <div><dt>Точные дубликаты</dt><dd>{quality.exact_duplicate_excess_rows} избыточных строк · {quality.exact_duplicate_rows_involved} строк вовлечено</dd></div>
          <div><dt>Константные столбцы</dt><dd>{quality.constant_columns.length ? quality.constant_columns.join(", ") : "нет"}</dd></div>
          <div><dt>Обработка</dt><dd>Не применялась; это диагностический отчёт</dd></div>
        </dl>
        <p className="table-note">Баланс классов: {Object.entries(quality.class_balance).map(([label, item]) => `${label} ${item.count} (${(item.fraction * 100).toFixed(1)}%)`).join(" · ")}.</p>
        <p className="table-note">{quality.outlier_method}. Экстремальные значения не удаляются и не обрезаются.</p>
      </section>}
      <section className="table-surface" aria-labelledby="features-title">
        <div className="table-heading"><h2 id="features-title">Исходные признаки</h2><span className="table-note">Имена строго из официального ARFF · без переименования</span></div>
        {selected && <FeatureExplorerControls models={models} selectors={selectors} budgets={budgets} selected={{ model: selected.model, selector: selected.selector, k: selected.k_original_features }} />}
        {frequency && sourceRunId && <p className="empty-copy">Условие: {modelLabel[selected!.model]} · {selectorLabel[selected!.selector]} · k={selected!.k_original_features}. Частоты из <Link href={`/runs/${sourceRunId}`}>{selected!.run_id}</Link> · {selected!.outer_fold_count} outer folds; mean pairwise Jaccard {metric(selected!.pairwise_jaccard_mean)}. Это устойчивость отбора, не causal importance.</p>}
        <Table size="small" aria-label="Канонические имена признаков"><TableHead><TableRow><TableCell>№</TableCell><TableCell>Исходный атрибут</TableCell><TableCell align="right">Наблюдаемый диапазон</TableCell><TableCell align="right">Экстремальные</TableCell><TableCell align="right">Впервые при k</TableCell><TableCell align="right">Частота отбора</TableCell></TableRow></TableHead><TableBody>{manifest.features.map((name, index) => {
          const stats = quality?.feature_statistics[name];
          return <TableRow key={name}><TableCell>{index + 1}</TableCell><TableCell>{name}</TableCell><TableCell align="right">{stats ? `${stats.minimum.toLocaleString("ru-RU")} … ${stats.maximum.toLocaleString("ru-RU")}` : "Не рассчитано"}</TableCell><TableCell align="right">{stats?.extreme_outlier_count ?? "Не рассчитано"}</TableCell><TableCell align="right">{firstSelectedBudget.get(name) ?? "не выбран"}</TableCell><TableCell align="right">{frequency ? metric(frequency[name], 2) : "Не рассчитано"}</TableCell></TableRow>;
        })}</TableBody></Table>
      </section>
      {selected && heatmapPoints.length > 0 && <section className="figure-surface" aria-labelledby="selection-map-title">
        <div className="figure-heading"><h2 id="selection-map-title">Частота отбора по бюджетам</h2><Chip label={`${modelLabel[selected.model]} · ${heatmapPoints.length}/${expectedBudgets} условий`} size="small" variant="outlined" /></div>
        <FeatureSelectionHeatmap features={manifest.features} points={heatmapPoints} />
        <p className="table-note">Каждая ячейка — реальная доля outer folds, в которых признак выбран. Отсутствующие k не интерполируются.</p>
      </section>}
      {quality && <section className="table-surface" aria-labelledby="correlation-title">
        <div className="table-heading"><h2 id="correlation-title">Корреляционный контекст</h2><span className="table-note">|Pearson r| ≥ {quality.high_correlation_threshold}</span></div>
        <Table size="small" aria-label="Сильно коррелирующие исходные признаки"><TableHead><TableRow><TableCell>Признак A</TableCell><TableCell>Признак B</TableCell><TableCell align="right">Pearson r</TableCell></TableRow></TableHead><TableBody>{quality.high_absolute_correlation_pairs.map(pair => <TableRow key={`${pair.left}-${pair.right}`}><TableCell>{pair.left}</TableCell><TableCell>{pair.right}</TableCell><TableCell align="right">{pair.pearson_r.toFixed(4)}</TableCell></TableRow>)}</TableBody></Table>
        <p className="table-note">{quality.correlation_note}</p>
      </section>}
    </> : !error && <section className="section-surface"><h2 className="section-title">Датасет не зарегистрирован</h2><p>Проверьте официальный UCI 602 через CLI; сведения появятся после строгой validation.</p></section>}
    <p className="scientific-footnote">PCA-компоненты не являются подмножеством исходных измеряемых признаков. Корреляции, importance и другие представления здесь не подменяются вымышленными данными.</p>
  </>;
}
