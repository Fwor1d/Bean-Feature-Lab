"use client";

import { useState } from "react";
import Link from "next/link";
import { Alert, Box, Button, Dialog, DialogActions, DialogContent, DialogTitle, FormControl, InputLabel, MenuItem, Select, TextField, Typography } from "@mui/material";
import { api, apiErrorMessage } from "@/lib/api/client";
import type { Experiment, ModelId, Run, SelectorId } from "@/lib/api/contracts";
import { modelLabel, selectorLabel } from "@/lib/science";

const CONTROL_POINTS = [1, 2, 4, 8, 12, 16];
const selectorOptions: { id: SelectorId; label: string }[] = [
  { id: "none", label: "Baseline · без отбора" },
  { id: "mutual_information", label: "Mutual Information" },
  { id: "anova", label: "ANOVA" },
  { id: "rfe", label: "RFE" },
  { id: "l1_logistic", label: "L1 Logistic · variable sparsity" },
  { id: "tree_importance", label: "Tree importance" },
  { id: "pca", label: "PCA" },
];
const compatibility: Record<ModelId, SelectorId[]> = {
  logistic_regression: ["none", "mutual_information", "rfe", "l1_logistic", "pca"],
  svm_rbf: ["none", "mutual_information", "anova", "rfe", "pca"],
  random_forest: ["none", "mutual_information", "anova", "tree_importance"],
  xgboost: ["none", "mutual_information", "anova", "tree_importance"],
  lightgbm: ["none", "mutual_information", "tree_importance"],
  mlp: ["none"],
};

function durationLabel(seconds: number | null) {
  if (seconds == null) return "Нет сопоставимых завершённых runs для оценки";
  if (seconds < 120) return `около ${Math.max(1, Math.round(seconds))} сек`;
  return `около ${Math.round(seconds / 60)} мин`;
}

export function ExperimentRegister({ initialExperiments, initialRuns, datasetVersion }: {
  initialExperiments: Experiment[];
  initialRuns: Run[];
  datasetVersion: string | null;
}) {
  const demoReadOnly = process.env.NEXT_PUBLIC_DEMO_READ_ONLY === "1";
  const [experiments, setExperiments] = useState(initialExperiments);
  const [name, setName] = useState("");
  const [model, setModel] = useState<ModelId>("logistic_regression");
  const [selector, setSelector] = useState<SelectorId>("mutual_information");
  const [budget, setBudget] = useState(16);
  const [l1C, setL1C] = useState(0.1);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [queued, setQueued] = useState<string | null>(null);
  const [review, setReview] = useState<Experiment | null>(null);
  const allowedSelectors = compatibility[model];
  const fixedControlPoint = selector === "anova" || selector === "rfe" || selector === "tree_importance";
  const historicalSecondsFor = (selectedModel: ModelId) => {
    const durations = initialRuns.flatMap(run => {
    const experiment = initialExperiments.find(item => item.id === run.experiment_id);
    if (run.status !== "COMPLETED" || experiment?.configuration.model !== selectedModel || !run.started_at || !run.finished_at) return [];
    const seconds = (Date.parse(run.finished_at) - Date.parse(run.started_at)) / 1000;
    return Number.isFinite(seconds) && seconds > 0 ? [seconds] : [];
    }).sort((a, b) => a - b);
    return durations.length ? durations[Math.floor(durations.length / 2)] : null;
  };
  const historicalSeconds = historicalSecondsFor(model);
  const create = async () => {
    setBusy(true); setError(null);
    try {
      const pca = selector === "pca";
      const sparse = selector === "l1_logistic";
      const item = await api.createExperiment({ name, configuration: {
        model, selector, budget_kind: pca ? "pca_components" : sparse ? "sparse_original_features" : "original_features",
        k_original_features: pca || sparse ? null : selector === "none" ? 16 : budget, n_components: pca ? budget : null,
        required_raw_feature_count: pca ? 16 : null, dataset_version: datasetVersion, seed: 42,
        selector_configuration: sparse ? { estimator: "l1_logistic", C: l1C } : {},
      } });
      setExperiments(current => [item, ...current]); setName("");
    } catch (caught) { setError(apiErrorMessage(caught)); }
    finally { setBusy(false); }
  };
  const queue = async (experimentId: number) => {
    setBusy(true); setError(null); setQueued(null);
    try { const run = await api.createRun(experimentId); setQueued(`${run.display_id} поставлен в очередь. Локальный worker выполнит протокол.`); setReview(null); }
    catch (caught) { setError(apiErrorMessage(caught)); }
    finally { setBusy(false); }
  };
  return <>
    <section className="section-surface" aria-labelledby="new-experiment-title">
      <h2 id="new-experiment-title" style={{ marginTop: 0, fontSize: 17 }}>Новая конфигурация</h2>
      <Typography color="text.secondary" sx={{ mb: 2, fontSize: 13 }}>{datasetVersion ? `Официальный датасет проверен: ${datasetVersion}. Сохраните конфигурацию, затем поставьте run в очередь worker.` : "Датасет не зарегистрирован. Перед запуском проверьте официальный UCI 602 через CLI."} Новый run использует полный nested CV; он может занять значительное время.</Typography>
      {demoReadOnly && <Alert severity="info" sx={{ mb: 2 }}>Публичная демонстрация доступна только для чтения. Создание и запуск научных заданий доступны локально через CLI или в обычном режиме разработки.</Alert>}
      <Box sx={{ display: "flex", gap: 1.5, flexWrap: "wrap", alignItems: "start" }}>
        <TextField label="Название" value={name} onChange={event => setName(event.target.value)} slotProps={{ htmlInput: { maxLength: 120 } }} sx={{ minWidth: 210, flex: 2 }} />
        <FormControl size="small" sx={{ minWidth: 180, flex: 1 }}><InputLabel id="experiment-model">Модель</InputLabel><Select labelId="experiment-model" label="Модель" value={model} onChange={event => {
          const next = event.target.value as ModelId; setModel(next);
          if (!compatibility[next].includes(selector)) { setSelector(compatibility[next].includes("mutual_information") ? "mutual_information" : "none"); setBudget(16); }
        }}>
          <MenuItem value="logistic_regression">Logistic Regression</MenuItem><MenuItem value="svm_rbf">SVM RBF</MenuItem><MenuItem value="random_forest">Random Forest</MenuItem><MenuItem value="xgboost">XGBoost</MenuItem><MenuItem value="lightgbm">LightGBM</MenuItem><MenuItem value="mlp">MLP</MenuItem>
        </Select></FormControl>
        <FormControl size="small" sx={{ minWidth: 190, flex: 1 }}><InputLabel id="experiment-selector">Метод</InputLabel><Select labelId="experiment-selector" label="Метод" value={selector} onChange={event => {
          const next = event.target.value as SelectorId; setSelector(next);
          if (next === "none") setBudget(16); else if (["anova", "rfe", "tree_importance"].includes(next) && !CONTROL_POINTS.includes(budget)) setBudget(4);
        }}>
          {selectorOptions.filter(item => allowedSelectors.includes(item.id)).map(item => <MenuItem value={item.id} key={item.id}>{item.label}</MenuItem>)}
        </Select></FormControl>
        {selector === "l1_logistic" ? <FormControl size="small" sx={{ width: 180 }}><InputLabel id="experiment-l1-c">L1 selector C</InputLabel><Select labelId="experiment-l1-c" label="L1 selector C" value={l1C} onChange={event => setL1C(Number(event.target.value))}>{[0.01, 0.1, 1, 10].map(value => <MenuItem key={value} value={value}>{value}</MenuItem>)}</Select></FormControl> : fixedControlPoint ? <FormControl size="small" sx={{ width: 180 }}><InputLabel id="experiment-budget">Контрольное k</InputLabel><Select labelId="experiment-budget" label="Контрольное k" value={budget} onChange={event => setBudget(Number(event.target.value))}>{CONTROL_POINTS.map(point => <MenuItem key={point} value={point}>{point} исходных</MenuItem>)}</Select></FormControl> :
          <TextField label={selector === "pca" ? "Компонент PCA" : "Исходных признаков"} type="number" value={selector === "none" ? 16 : budget} disabled={selector === "none"} onChange={event => setBudget(Number(event.target.value))} slotProps={{ htmlInput: { min: 1, max: 16 } }} sx={{ width: 160 }} />}
        <Button variant="contained" onClick={create} disabled={demoReadOnly || busy || !name.trim() || !datasetVersion || (selector !== "none" && selector !== "l1_logistic" && (!Number.isInteger(budget) || budget < 1 || budget > 16))} sx={{ minHeight: 40 }}>Сохранить</Button>
      </Box>
      <Typography color="text.secondary" sx={{ mt: 1.5, fontSize: 12 }}>1 условие · 15 outer folds · 4 inner folds · историческая медиана для {modelLabel[model]}: {durationLabel(historicalSeconds)}. Оценка ориентировочная и не является benchmark.</Typography>
      {error && <Alert severity="error" sx={{ mt: 2 }}>{error}</Alert>}
      {queued && <Alert severity="info" sx={{ mt: 2 }}>{queued} <Link href="/runs">Открыть журнал</Link></Alert>}
    </section>
    <section className="section-surface" style={{ marginTop: 14 }} aria-labelledby="registry-title">
      <h2 id="registry-title" style={{ marginTop: 0, fontSize: 17 }}>Реестр конфигураций</h2>
      {experiments.length === 0 ? <Typography color="text.secondary" sx={{ fontSize: 14 }}>Конфигураций нет. Сохраните первую после проверки датасета.</Typography> :
        <Box component="ul" sx={{ listStyle: "none", m: 0, p: 0 }}>
          {experiments.map(item => <Box component="li" key={item.id} sx={{ display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: 2, py: 1.5, borderTop: "1px solid #dce3ea" }}><div><strong>{item.name}</strong><Typography color="text.secondary" sx={{ fontSize: 13 }}>{modelLabel[item.configuration.model]} · {selectorLabel[item.configuration.selector]} · {item.configuration.budget_kind === "pca_components" ? `${item.configuration.n_components} компонент PCA` : item.configuration.budget_kind === "sparse_original_features" ? `L1 C=${String(item.configuration.selector_configuration?.C)} · фактическое k по folds` : `${item.configuration.k_original_features} исходных признаков`} · {item.configuration.evaluation_mode === "smoke" ? "Smoke" : "Полный протокол"}</Typography></div><Button variant="outlined" size="small" disabled={demoReadOnly || busy || !datasetVersion} onClick={() => setReview(item)}>Проверить и запустить</Button></Box>)}
        </Box>}
    </section>
    <Dialog open={review !== null} onClose={() => !busy && setReview(null)} fullWidth maxWidth="sm" aria-labelledby="run-review-title">
      <DialogTitle id="run-review-title">Проверка перед постановкой в очередь</DialogTitle>
      <DialogContent dividers>
        {review && <>
          <Typography sx={{ mb: 1.5 }}>Новый run для «{review.name}» запустит реальное вычисление. Условия сохраняются вместе с run и не изменяются после просмотра результата.</Typography>
          <dl className="detail-list">
            <div><dt>Dataset</dt><dd>{review.configuration.dataset_version ?? "Не зарегистрирован"}</dd></div>
            <div><dt>Модель / метод</dt><dd>{modelLabel[review.configuration.model]} · {selectorLabel[review.configuration.selector]}</dd></div>
            <div><dt>Представление</dt><dd>{review.configuration.budget_kind === "pca_components" ? `${review.configuration.n_components} компонент PCA при 16 исходных измерениях` : review.configuration.budget_kind === "sparse_original_features" ? `L1 sparse path C=${String(review.configuration.selector_configuration?.C)}; число ненулевых признаков измеряется в каждом fold` : `${review.configuration.k_original_features} исходных признаков`}</dd></div>
            <div><dt>Протокол</dt><dd>{review.configuration.evaluation_mode === "smoke" ? "Технический smoke" : "Outer: 5 folds × 3 repeats; inner: 4 folds"} · seed {review.configuration.seed}</dd></div>
            <div><dt>Поиск</dt><dd>{JSON.stringify(review.configuration.search_space ?? {})}</dd></div>
            <div><dt>Ожидаемый объём</dt><dd>1 условие · 15 outer folds · inner CV 4 folds · {durationLabel(historicalSecondsFor(review.configuration.model))}</dd></div>
            <div><dt>Ресурсы</dt><dd>Время и latency измеряются; peak memory пока не рассчитано.</dd></div>
          </dl>
        </>}
      </DialogContent>
      <DialogActions><Button onClick={() => setReview(null)} disabled={busy}>Отмена</Button><Button variant="contained" onClick={() => review && queue(review.id)} disabled={busy || !review}>Поставить в очередь</Button></DialogActions>
    </Dialog>
  </>;
}
