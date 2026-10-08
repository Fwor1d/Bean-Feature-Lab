import Link from "next/link";
import { notFound } from "next/navigation";
import { Alert, Chip, Divider, Table, TableBody, TableCell, TableContainer, TableHead, TableRow } from "@mui/material";
import { RunExports } from "@/components/RunExports";
import { FoldGrid } from "@/components/FoldGrid";
import { api, apiErrorMessage, ApiError } from "@/lib/api/client";
import type { Experiment, FoldResult, Run, RunDetail, RunResources, RunSummary, RunVerification } from "@/lib/api/contracts";
import { metric, modelLabel, runLabel, selectorLabel, utcTime } from "@/lib/science";
import { selectFold } from "@/lib/view-selection";

const shortHash = (value: string) => <code title={value}>{value}</code>;

export default async function RunDetailPage({ params, searchParams }: {
  params: Promise<{ id: string }>;
  searchParams: Promise<{ fold?: string }>;
}) {
  const id = Number((await params).id);
  if (!Number.isSafeInteger(id) || id < 1) notFound();
  const requestedFold = (await searchParams).fold;
  let run: Run | null = null;
  let experiment: Experiment | null = null;
  let summary: RunSummary | null = null;
  let detail: RunDetail | null = null;
  let folds: FoldResult[] = [];
  let verification: RunVerification | null = null;
  let resources: RunResources | null = null;
  let error: string | null = null;
  try {
    run = await api.run(id);
    [experiment, summary] = await Promise.all([api.experiments().then(items => items.find(item => item.id === run!.experiment_id) ?? null), api.runSummary(id)]);
    if (run.status === "COMPLETED") [detail, folds, verification, resources] = await Promise.all([
      api.runDetail(id), api.runFolds(id), api.runVerification(id), api.runResources(id),
    ]);
  } catch (caught) {
    if (caught instanceof ApiError && caught.status === 404) notFound();
    error = apiErrorMessage(caught);
  }
  const selected = selectFold(folds, requestedFold);
  const config = experiment?.configuration;
  const scientific = summary?.summary;
  const classes = detail?.dataset_manifest.classes ?? [];
  return <>
    <p className="breadcrumb"><Link href="/runs">Запуски</Link> / {run?.display_id ?? `#${id}`}</p>
    <h1 className="page-heading">{run?.display_id ?? "Детали запуска"}</h1>
    {error && <Alert severity="warning" sx={{ mb: 2 }}>{error} <Link href={`/runs/${id}`}>Повторить запрос</Link></Alert>}
    {!error && requestedFold !== undefined && !selected && <Alert severity="info" sx={{ mb: 2 }}>Запрошенный fold недоступен. Выберите существующий fold в таблице или <Link href={`/runs/${id}`}>сбросьте выбор</Link>.</Alert>}
    {run && <>
      <p className="page-question">{experiment?.name ?? `Эксперимент #${run.experiment_id}`} · {config ? modelLabel[config.model] : "Модель не найдена"} · {config ? selectorLabel[config.selector] : "Метод не найден"}</p>
      <div className="status-line" style={{ marginBottom: 16 }}><Chip label={runLabel[run.status]} size="small" color={run.status === "COMPLETED" ? "success" : run.status === "FAILED" ? "error" : "default"} variant="outlined" />
        <span className="table-note">Создан {utcTime(run.created_at)} · начало {utcTime(run.started_at)} · завершён {utcTime(run.finished_at)}</span></div>
      {run.status === "RUNNING" || run.status === "QUEUED" ? <Alert severity="info" sx={{ mb: 2 }}>Результат ещё не рассчитан. Обновите страницу после завершения worker.</Alert> : null}
      {run.error && <Alert severity="error" sx={{ mb: 2 }}>Ошибка исполнения: {run.error}. Метрики этого run не публикуются.</Alert>}
      <section className="section-surface" aria-labelledby="summary-title">
        <h2 id="summary-title" className="section-title">Научная сводка</h2>
        {scientific ? <>
          {scientific.evaluation_mode === "smoke" && <Alert severity="warning" sx={{ mb: 2 }}>Технический smoke · 2 outer folds. Не является итоговым научным результатом.</Alert>}
          <dl className="metric-list"><div><dt>Macro-F1, среднее</dt><dd>{metric(scientific.macro_f1_mean)}</dd></div><div><dt>Accuracy, среднее</dt><dd>{metric(scientific.accuracy_mean)}</dd></div><div><dt>Outer folds</dt><dd>{scientific.outer_fold_count}</dd></div><div><dt>Inner folds</dt><dd>{scientific.inner_fold_count}</dd></div><div><dt>Достаточное k</dt><dd>{metric(scientific.sufficient_k, 0)}</dd></div></dl>
          {scientific.observed_nonzero_feature_counts?.length ? <p className="table-note">L1 sparse path: фактическое число ненулевых исходных признаков по outer folds — {scientific.observed_nonzero_feature_counts.join(", ")}. Это наблюдаемая sparsity, а не fixed-k budget.</p> : null}
          <p className="table-note">Разброс Macro-F1 по зависимым folds (описательный SD): {metric(scientific.macro_f1_fold_sd_descriptive)}. {scientific.dispersion_note}</p>
          <p className="table-note">Протокол: {scientific.cv_protocol_version} · seed {scientific.seed}. PCA-компоненты не считаются исходными признаками.</p>
          <p className="table-note">Sufficient-k в этой сводке — поле исходного immutable artifact. Позднее рассчитанные paired decisions сохранены отдельно: <Link href={`/feature-budget?model=${scientific.model}`}>открыть Core MI sufficient-k анализ</Link>. Старый результат не перезаписывается.</p>
        </> : <p>Не рассчитано. Полные outer folds ещё не сохранены.</p>}
      </section>
      {detail && <section className="section-surface stack-section" aria-labelledby="provenance-title">
        <h2 id="provenance-title" className="section-title">Конфигурация и происхождение</h2>
        {verification && <div className="status-line" style={{ marginBottom: 16 }}><Chip label={verification.verified ? "Artifact и run верифицированы" : "Верификация не пройдена"} color={verification.verified ? "success" : "error"} size="small" variant="outlined" /><span>{Object.values(verification.checks).filter(Boolean).length}/{Object.keys(verification.checks).length} проверок</span></div>}
        <dl className="detail-list">
          <div><dt>Бюджет</dt><dd>{config?.budget_kind === "pca_components" ? `${config.n_components} компонент PCA · нужны 16 исходных признаков` : config?.budget_kind === "sparse_original_features" ? `L1 sparse path C=${String(config.selector_configuration?.C)} · фактическое k по folds` : `${config?.k_original_features} исходных признаков`}</dd></div>
          <div><dt>Dataset</dt><dd>{detail.dataset_manifest.source} · ID {detail.dataset_manifest.source_id} · {detail.dataset_manifest.dataset_version}</dd></div>
          <div><dt>ARFF SHA-256</dt><dd>{shortHash(detail.dataset_manifest.arff_sha256)}</dd></div>
          <div><dt>Outer split set</dt><dd>{shortHash(scientific?.outer_split_set_sha256 ?? "—")}</dd></div>
          <div><dt>Git</dt><dd>{detail.provenance.git_commit ?? "Не определён"}{detail.provenance.git_dirty ? " · рабочая копия изменена" : " · чистая рабочая копия"}</dd></div>
          <div><dt>Source fingerprint</dt><dd>{shortHash(detail.provenance.source_tree_sha256)}</dd></div>
          <div><dt>Environment</dt><dd>Python {detail.provenance.python_version} · {detail.provenance.platform}</dd></div>
          <div><dt>Artifact</dt><dd>{detail.artifact_verified ? "SHA-256 проверен" : "Не подтверждён"} · {detail.result_artifact}<br />{shortHash(detail.result_sha256)}</dd></div>
        </dl>
        {verification?.errors.length ? <Alert severity="error" sx={{ mt: 2 }}>{verification.errors.join(" · ")}</Alert> : null}
        {verification?.verified && <RunExports id={id} selection={Boolean(scientific?.feature_stability)} />}
        <details><summary>Поисковое пространство и версии пакетов</summary><pre className="metadata-pre">{JSON.stringify({ search_space: config?.search_space, package_versions: detail.provenance.package_versions, fingerprint: detail.fingerprint }, null, 2)}</pre></details>
      </section>}
      {scientific?.feature_stability && <section className="section-surface stack-section" aria-labelledby="stability-title">
        <h2 id="stability-title" className="section-title">Устойчивость отбора исходных признаков</h2>
        <p className="table-note">Jaccard между fold-наборами: {metric(scientific.feature_stability.pairwise_jaccard_mean)} · описательный, repeated-CV folds зависимы.</p>
        <div className="feature-frequency">{Object.entries(scientific.feature_stability.selection_frequency).filter(([, frequency]) => frequency > 0).sort((a, b) => b[1] - a[1]).map(([name, frequency]) => <div key={name}><span>{name}</span><strong>{metric(frequency, 2)}</strong></div>)}</div>
      </section>}
      {resources && <section className="section-surface stack-section" aria-labelledby="resources-title">
        <h2 id="resources-title" className="section-title">Инженерные измерения</h2>
        <dl className="metric-list">
          <div><dt>Nested search, все folds</dt><dd>{metric(resources.total_nested_search_seconds, 2)} с</dd></div>
          <div><dt>Outer refit, все folds</dt><dd>{metric(resources.total_outer_refit_seconds, 2)} с</dd></div>
          <div><dt>Latency batch=1, median</dt><dd>{resources.inference_latency_ms.single_row ? `${metric(resources.inference_latency_ms.single_row.median, 3)} мс` : "Не рассчитано"}</dd></div>
          <div><dt>Latency batch=1000, median</dt><dd>{resources.inference_latency_ms.batch_1000 ? `${metric(resources.inference_latency_ms.batch_1000.median, 3)} мс` : "Не рассчитано"}</dd></div>
          <div><dt>Pipeline size, median</dt><dd>{resources.serialized_pipeline_bytes ? `${Math.round(resources.serialized_pipeline_bytes.median).toLocaleString("ru-RU")} байт` : "Не рассчитано"}</dd></div>
          <div><dt>Peak memory</dt><dd>{resources.peak_memory_bytes ? `${Math.round(resources.peak_memory_bytes.median).toLocaleString("ru-RU")} байт` : "Не рассчитано"}</dd></div>
          <div><dt>Incremental peak RSS</dt><dd>{resources.process_tree_measurement?.incremental_peak_rss_bytes != null ? `${resources.process_tree_measurement.incremental_peak_rss_bytes.toLocaleString("ru-RU")} байт` : "Не рассчитано"}</dd></div>
        </dl>
        <p className="table-note">{resources.timing_note} {resources.peak_memory_reason} {resources.process_tree_measurement?.note}</p>
      </section>}
      {folds.length > 0 && <section className="table-surface stack-section" aria-labelledby="folds-title"><div className="table-heading"><h2 id="folds-title">Outer-fold результаты</h2><span className="table-note">{folds.length} из {scientific?.outer_fold_count} · ссылки открывают fold</span></div><FoldGrid runId={id} folds={folds} /></section>}
      {selected && <section className="section-surface stack-section" aria-labelledby="fold-detail-title">
        <h2 id="fold-detail-title" className="section-title">Fold {selected.fold_id} · диагностика</h2>
        <p className="table-note">Macro-F1 {metric(selected.macro_f1)} · Accuracy {metric(selected.accuracy)} · ROC AUC OvR {metric(selected.roc_auc_ovr_macro)}. Search {metric(selected.search_seconds, 2)} с · final fit {metric(selected.refit_seconds, 2)} с · сериализованный pipeline {selected.serialized_pipeline_bytes.toLocaleString("ru-RU")} байт. Peak memory: {selected.peak_memory_bytes == null ? "Не рассчитано" : `${selected.peak_memory_bytes.toLocaleString("ru-RU")} байт`}.</p>
        <p className="table-note">Выбрано на training fold: {selected.selected_original_features?.join(", ") ?? "PCA-компоненты / не применимо"}. Параметры inner CV: {JSON.stringify(selected.best_params)}.</p>
        <Divider sx={{ my: 2 }} />
        <h3 className="subsection-title">Confusion matrix · только fold {selected.fold_id}</h3>
        <TableContainer sx={{ maxWidth: 780, overflowX: "auto" }}><Table size="small" aria-label={`Матрица ошибок fold ${selected.fold_id}`}><TableHead><TableRow><TableCell>True \ Pred</TableCell>{classes.map(name => <TableCell key={name} align="right">{name}</TableCell>)}</TableRow></TableHead><TableBody>{selected.confusion_matrix.map((row, index) => <TableRow key={classes[index]}><TableCell component="th" scope="row">{classes[index]}</TableCell>{row.map((count, column) => <TableCell key={classes[column]} align="right">{count}</TableCell>)}</TableRow>)}</TableBody></Table></TableContainer>
        <details><summary>Recall по классам, latency полного pipeline и split hash</summary><pre className="metadata-pre">{JSON.stringify({ per_class_recall: selected.per_class_recall, inference_latency: selected.inference_latency, split_sha256: selected.split_sha256, representation: selected.representation }, null, 2)}</pre></details>
      </section>}
    </>}
  </>;
}
