"use client";

import { useState } from "react";
import Link from "next/link";
import { Alert, Box, Button, Dialog, DialogActions, DialogContent, DialogTitle, FormControl, InputLabel, MenuItem, Select, TextField, Typography } from "@mui/material";
import { api, apiErrorMessage } from "@/lib/api/client";
import type { Experiment, ModelId, SelectorId } from "@/lib/api/contracts";
import { modelLabel, selectorLabel } from "@/lib/science";

export function ExperimentRegister({ initialExperiments, datasetVersion }: { initialExperiments: Experiment[]; datasetVersion: string | null }) {
  const demoReadOnly = process.env.NEXT_PUBLIC_DEMO_READ_ONLY === "1";
  const [experiments, setExperiments] = useState(initialExperiments);
  const [name, setName] = useState("");
  const [model, setModel] = useState<ModelId>("logistic_regression");
  const [selector, setSelector] = useState<SelectorId>("mutual_information");
  const [budget, setBudget] = useState(16);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [queued, setQueued] = useState<string | null>(null);
  const [review, setReview] = useState<Experiment | null>(null);
  const create = async () => {
    setBusy(true); setError(null);
    try {
      const pca = selector === "pca";
      const item = await api.createExperiment({ name, configuration: {
        model, selector, budget_kind: pca ? "pca_components" : "original_features",
        k_original_features: pca ? null : selector === "none" ? 16 : budget, n_components: pca ? budget : null,
        required_raw_feature_count: pca ? 16 : null, dataset_version: datasetVersion, seed: 42,
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
        <FormControl size="small" sx={{ minWidth: 180, flex: 1 }}><InputLabel id="experiment-model">Модель</InputLabel><Select labelId="experiment-model" label="Модель" value={model} onChange={event => setModel(event.target.value as ModelId)}>
          <MenuItem value="logistic_regression">Logistic Regression</MenuItem><MenuItem value="svm_rbf">SVM RBF</MenuItem><MenuItem value="random_forest">Random Forest</MenuItem><MenuItem value="xgboost">XGBoost</MenuItem><MenuItem value="lightgbm">LightGBM</MenuItem><MenuItem value="mlp">MLP</MenuItem>
        </Select></FormControl>
        <FormControl size="small" sx={{ minWidth: 190, flex: 1 }}><InputLabel id="experiment-selector">Метод</InputLabel><Select labelId="experiment-selector" label="Метод" value={selector} onChange={event => setSelector(event.target.value as SelectorId)}>
          <MenuItem value="none">Baseline · без отбора</MenuItem><MenuItem value="mutual_information">Mutual Information</MenuItem><MenuItem value="anova">ANOVA</MenuItem><MenuItem value="rfe">RFE</MenuItem><MenuItem value="l1_logistic">L1 Logistic</MenuItem><MenuItem value="tree_importance">Tree importance</MenuItem><MenuItem value="pca">PCA</MenuItem>
        </Select></FormControl>
        <TextField label={selector === "pca" ? "Компонент PCA" : "Исходных признаков"} type="number" value={selector === "none" ? 16 : budget} disabled={selector === "none"} onChange={event => setBudget(Number(event.target.value))} slotProps={{ htmlInput: { min: 1, max: 16 } }} sx={{ width: 160 }} />
        <Button variant="contained" onClick={create} disabled={demoReadOnly || busy || !name.trim() || !datasetVersion || (selector !== "none" && (!Number.isInteger(budget) || budget < 1 || budget > 16))} sx={{ minHeight: 40 }}>Сохранить</Button>
      </Box>
      {error && <Alert severity="error" sx={{ mt: 2 }}>{error}</Alert>}
      {queued && <Alert severity="info" sx={{ mt: 2 }}>{queued} <Link href="/runs">Открыть журнал</Link></Alert>}
    </section>
    <section className="section-surface" style={{ marginTop: 14 }} aria-labelledby="registry-title">
      <h2 id="registry-title" style={{ marginTop: 0, fontSize: 17 }}>Реестр конфигураций</h2>
      {experiments.length === 0 ? <Typography color="text.secondary" sx={{ fontSize: 14 }}>Конфигураций нет. Сохраните первую после проверки датасета.</Typography> :
        <Box component="ul" sx={{ listStyle: "none", m: 0, p: 0 }}>
          {experiments.map(item => <Box component="li" key={item.id} sx={{ display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: 2, py: 1.5, borderTop: "1px solid #dce3ea" }}><div><strong>{item.name}</strong><Typography color="text.secondary" sx={{ fontSize: 13 }}>{modelLabel[item.configuration.model]} · {selectorLabel[item.configuration.selector]} · {item.configuration.budget_kind === "pca_components" ? `${item.configuration.n_components} компонент PCA` : `${item.configuration.k_original_features} исходных признаков`} · {item.configuration.evaluation_mode === "smoke" ? "Smoke" : "Полный протокол"}</Typography></div><Button variant="outlined" size="small" disabled={demoReadOnly || busy || !datasetVersion} onClick={() => setReview(item)}>Проверить и запустить</Button></Box>)}
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
            <div><dt>Представление</dt><dd>{review.configuration.budget_kind === "pca_components" ? `${review.configuration.n_components} компонент PCA при 16 исходных измерениях` : `${review.configuration.k_original_features} исходных признаков`}</dd></div>
            <div><dt>Протокол</dt><dd>{review.configuration.evaluation_mode === "smoke" ? "Технический smoke" : "Outer: 5 folds × 3 repeats; inner: 4 folds"} · seed {review.configuration.seed}</dd></div>
            <div><dt>Поиск</dt><dd>{JSON.stringify(review.configuration.search_space ?? {})}</dd></div>
            <div><dt>Ресурсы</dt><dd>Время и latency измеряются; peak memory пока не рассчитано.</dd></div>
          </dl>
        </>}
      </DialogContent>
      <DialogActions><Button onClick={() => setReview(null)} disabled={busy}>Отмена</Button><Button variant="contained" onClick={() => review && queue(review.id)} disabled={busy || !review}>Поставить в очередь</Button></DialogActions>
    </Dialog>
  </>;
}
