import Link from "next/link";
import { Alert, Chip, Table, TableBody, TableCell, TableHead, TableRow } from "@mui/material";
import { api, apiErrorMessage } from "@/lib/api/client";
import type { DatasetManifest, RunSummary } from "@/lib/api/contracts";
import { metric } from "@/lib/science";

export default async function FeaturesPage() {
  let manifest: DatasetManifest | null = null;
  let selected: RunSummary | null = null;
  let sourceRunId: number | null = null;
  let error: string | null = null;
  try {
    const [datasets, runs, experiments] = await Promise.all([api.datasets(), api.runs(), api.experiments()]);
    if (datasets[0]) manifest = await api.datasetManifest(datasets[0].id);
    const configurations = new Map(experiments.map(item => [item.id, item.configuration]));
    const source = runs.find(run => run.status === "COMPLETED" && configurations.get(run.experiment_id)?.selector === "mutual_information" && configurations.get(run.experiment_id)?.evaluation_mode === "protocol");
    if (source) { selected = await api.runSummary(source.id); sourceRunId = source.id; }
  } catch (caught) { error = apiErrorMessage(caught); }
  const frequency = selected?.summary?.feature_stability?.selection_frequency;
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
      <section className="table-surface" aria-labelledby="features-title">
        <div className="table-heading"><h2 id="features-title">Исходные признаки</h2><span className="table-note">Имена строго из официального ARFF · без переименования</span></div>
        {frequency && sourceRunId && <p className="empty-copy">Частота отбора из <Link href={`/runs/${sourceRunId}`}>{selected?.run_id}</Link> · {selected?.summary?.outer_fold_count} outer folds. Это описательная частота, не значение важности.</p>}
        <Table size="small" aria-label="Канонические имена признаков"><TableHead><TableRow><TableCell>№</TableCell><TableCell>Исходный атрибут</TableCell><TableCell align="right">Частота отбора</TableCell></TableRow></TableHead><TableBody>{manifest.features.map((name, index) => <TableRow key={name}><TableCell>{index + 1}</TableCell><TableCell>{name}</TableCell><TableCell align="right">{frequency ? metric(frequency[name], 2) : "Не рассчитано"}</TableCell></TableRow>)}</TableBody></Table>
      </section>
    </> : !error && <section className="section-surface"><h2 className="section-title">Датасет не зарегистрирован</h2><p>Проверьте официальный UCI 602 через CLI; сведения появятся после строгой validation.</p></section>}
    <p className="scientific-footnote">PCA-компоненты не являются подмножеством исходных измеряемых признаков. Корреляции, importance и другие представления здесь не подменяются вымышленными данными.</p>
  </>;
}
