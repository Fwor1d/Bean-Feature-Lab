"use client";

import { useState } from "react";
import { Alert, Box, Button, FormControl, InputLabel, MenuItem, Select, TextField, Typography } from "@mui/material";
import { api, apiErrorMessage } from "@/lib/api/client";
import type { Experiment, ModelId, SelectorId } from "@/lib/api/contracts";

export function ExperimentRegister({ initialExperiments }: { initialExperiments: Experiment[] }) {
  const [experiments, setExperiments] = useState(initialExperiments);
  const [name, setName] = useState("");
  const [model, setModel] = useState<ModelId>("logistic_regression");
  const [selector, setSelector] = useState<SelectorId>("mutual_information");
  const [budget, setBudget] = useState(16);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const create = async () => {
    setBusy(true); setError(null);
    try {
      const pca = selector === "pca";
      const item = await api.createExperiment({ name, configuration: {
        model, selector, budget_kind: pca ? "pca_components" : "original_features",
        k_original_features: pca ? null : budget, n_components: pca ? budget : null,
        required_raw_feature_count: pca ? 16 : null, dataset_version: null, seed: 42,
      } });
      setExperiments(current => [item, ...current]); setName("");
    } catch (caught) { setError(apiErrorMessage(caught)); }
    finally { setBusy(false); }
  };
  return <>
    <section className="section-surface" aria-labelledby="new-experiment-title">
      <h2 id="new-experiment-title" style={{ marginTop: 0, fontSize: 17 }}>Новая конфигурация</h2>
      <Typography color="text.secondary" sx={{ mb: 2, fontSize: 13 }}>Сохранить определение можно сейчас; научный запуск ещё не реализован. Датасет не выбран.</Typography>
      <Box sx={{ display: "flex", gap: 1.5, flexWrap: "wrap", alignItems: "start" }}>
        <TextField label="Название" value={name} onChange={event => setName(event.target.value)} slotProps={{ htmlInput: { maxLength: 120 } }} sx={{ minWidth: 210, flex: 2 }} />
        <FormControl size="small" sx={{ minWidth: 180, flex: 1 }}><InputLabel id="experiment-model">Модель</InputLabel><Select labelId="experiment-model" label="Модель" value={model} onChange={event => setModel(event.target.value as ModelId)}>
          <MenuItem value="logistic_regression">Logistic Regression</MenuItem><MenuItem value="svm_rbf">SVM RBF</MenuItem><MenuItem value="random_forest">Random Forest</MenuItem><MenuItem value="xgboost">XGBoost</MenuItem><MenuItem value="lightgbm">LightGBM</MenuItem><MenuItem value="mlp">MLP</MenuItem>
        </Select></FormControl>
        <FormControl size="small" sx={{ minWidth: 190, flex: 1 }}><InputLabel id="experiment-selector">Метод</InputLabel><Select labelId="experiment-selector" label="Метод" value={selector} onChange={event => setSelector(event.target.value as SelectorId)}>
          <MenuItem value="mutual_information">Mutual Information</MenuItem><MenuItem value="anova">ANOVA</MenuItem><MenuItem value="rfe">RFE</MenuItem><MenuItem value="l1_logistic">L1 Logistic</MenuItem><MenuItem value="tree_importance">Tree importance</MenuItem><MenuItem value="pca">PCA</MenuItem>
        </Select></FormControl>
        <TextField label={selector === "pca" ? "Компонент PCA" : "Исходных признаков"} type="number" value={budget} onChange={event => setBudget(Number(event.target.value))} slotProps={{ htmlInput: { min: 1, max: 16 } }} sx={{ width: 160 }} />
        <Button variant="contained" onClick={create} disabled={busy || !name.trim() || budget < 1 || budget > 16} sx={{ minHeight: 40 }}>Сохранить</Button>
      </Box>
      {error && <Alert severity="error" sx={{ mt: 2 }}>{error}</Alert>}
    </section>
    <section className="section-surface" style={{ marginTop: 14 }} aria-labelledby="registry-title">
      <h2 id="registry-title" style={{ marginTop: 0, fontSize: 17 }}>Реестр конфигураций</h2>
      {experiments.length === 0 ? <Typography color="text.secondary" sx={{ fontSize: 14 }}>Конфигураций нет. Сохраните первую — она останется без результатов до настоящего запуска.</Typography> :
        <Box component="ul" sx={{ listStyle: "none", m: 0, p: 0 }}>
          {experiments.map(item => <Box component="li" key={item.id} sx={{ display: "flex", justifyContent: "space-between", gap: 2, py: 1.5, borderTop: "1px solid #dce3ea" }}><strong>{item.name}</strong><span>{item.configuration.model} · {item.configuration.selector} · {item.configuration.budget_kind === "pca_components" ? `${item.configuration.n_components} компонент` : `${item.configuration.k_original_features} исходных признаков`}</span></Box>)}
        </Box>}
    </section>
  </>;
}
