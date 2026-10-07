import { Alert, Chip } from "@mui/material";
import { api, apiErrorMessage } from "@/lib/api/client";
import { ClassifierForm } from "./ClassifierForm";

export default async function ClassifierPage() {
  let model: Awaited<ReturnType<typeof api.classifierModel>> | null = null;
  let benchmark: Awaited<ReturnType<typeof api.classifierBenchmark>> | null = null;
  let error: string | null = null;
  try {
    model = await api.classifierModel();
    benchmark = await api.classifierBenchmark().catch(() => null);
  } catch (caught) { error = apiErrorMessage(caught); }
  return <>
    <h1 className="page-heading">Классификатор</h1>
    <p className="page-question">Применение финальной модели к табличным данным — отдельный inference-сценарий, не экспериментальная оценка.</p>
    {model && <section className="section-surface" aria-labelledby="model-registry-title">
      <h2 id="model-registry-title" className="section-title">Активная deployment model</h2>
      <div className="status-line"><Chip label={model.deployment_status ?? "ACTIVE"} color="success" size="small" variant="outlined" /><span>{model.model_id} · version {model.model_version ?? "legacy"}</span></div>
      <dl className="detail-list"><div><dt>Источник</dt><dd>{model.source_run} · {model.model_family} · 16 исходных признаков</dd></div><div><dt>Dataset</dt><dd>UCI 602 · <code>{model.dataset_sha256}</code></dd></div><div><dt>Artifact SHA-256</dt><dd><code>{model.artifact_sha256 ?? "legacy metadata"}</code></dd></div></dl>
      {benchmark ? <p className="table-note">Изолированный benchmark: batch=1 median {benchmark.latency.single_row.median_ms.toFixed(3)} мс, p95 {benchmark.latency.single_row.p95_ms.toFixed(3)} мс · peak process-tree RSS {(benchmark.peak_process_tree_rss_bytes / 1024 / 1024).toFixed(1)} MiB · incremental {(benchmark.incremental_peak_rss_bytes / 1024 / 1024).toFixed(1)} MiB. {benchmark.note}</p> : <p className="table-note">Peak memory и изолированный latency benchmark: не рассчитано.</p>}
    </section>}
    {model ? <ClassifierForm model={model} /> : <Alert severity="warning">{error} Модель не зарегистрирована; выполните <code>beanfeature classifier train</code>.</Alert>}
  </>;
}
