"use client";

import { useState } from "react";
import { Alert, Box, Button, CircularProgress, Stack, Table, TableBody, TableCell, TableContainer, TableHead, TableRow, TextField, Typography } from "@mui/material";
import { api, apiErrorMessage } from "@/lib/api/client";
import type { ClassifierModel, ClassifierPrediction } from "@/lib/api/contracts";

export function ClassifierForm({ model }: { model: ClassifierModel }) {
  const [values, setValues] = useState<Record<string, string>>({});
  const [result, setResult] = useState<ClassifierPrediction | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function fillExample() {
    setBusy(true); setError(null); setResult(null);
    try {
      const example = await api.classifierExample();
      setValues(Object.fromEntries(model.feature_names.map(name => [name, String(example.features[name])])));
    } catch (caught) { setError(apiErrorMessage(caught)); }
    finally { setBusy(false); }
  }

  async function predict() {
    const features: Record<string, number> = {};
    for (const name of model.feature_names) {
      const raw = values[name]?.trim();
      if (!raw || !Number.isFinite(Number(raw))) {
        setError(`Введите конечное числовое значение для ${name}.`);
        return;
      }
      features[name] = Number(raw);
    }
    setBusy(true); setError(null); setResult(null);
    try { setResult(await api.predict(features)); }
    catch (caught) { setError(apiErrorMessage(caught)); }
    finally { setBusy(false); }
  }

  return <>
    <section className="section-surface" aria-labelledby="prediction-title">
      <h2 id="prediction-title" style={{ marginTop: 0, fontSize: 17 }}>Табличный ввод</h2>
      <Typography color="text.secondary" sx={{ mb: 1.5, fontSize: 13 }}>16 канонических признаков UCI · {model.model_family} · {model.source_run}. «Заполнить пример» берёт реальную строку из проверенного датасета.</Typography>
      <TableContainer sx={{ maxHeight: 445, border: "1px solid", borderColor: "divider" }}>
        <Table stickyHeader size="small" aria-label="Входные признаки фасоли">
          <TableHead><TableRow><TableCell>Признак UCI</TableCell><TableCell>Значение</TableCell></TableRow></TableHead>
          <TableBody>{model.feature_names.map(name => <TableRow key={name}>
            <TableCell sx={{ fontFamily: "monospace", fontSize: 12 }}>{name}</TableCell>
            <TableCell><TextField size="small" type="number" fullWidth value={values[name] ?? ""} onChange={event => setValues(previous => ({ ...previous, [name]: event.target.value }))} slotProps={{ htmlInput: { step: "any", "aria-label": name } }} /></TableCell>
          </TableRow>)}</TableBody>
        </Table>
      </TableContainer>
      <Stack direction="row" spacing={1} sx={{ mt: 2, flexWrap: "wrap", gap: 1 }}>
        <Button variant="contained" onClick={predict} disabled={busy}>{busy ? <CircularProgress size={20} color="inherit" /> : "Предсказать"}</Button>
        <Button variant="outlined" onClick={fillExample} disabled={busy}>Заполнить пример</Button>
        <Button variant="text" onClick={() => { setValues({}); setResult(null); setError(null); }} disabled={busy}>Очистить</Button>
      </Stack>
      {error && <Alert severity="error" sx={{ mt: 2 }}>{error}</Alert>}
    </section>
    {result && <section className="section-surface" aria-live="polite" style={{ marginTop: 16 }}>
      <h2 style={{ marginTop: 0, fontSize: 17 }}>Результат предсказания</h2>
      <Typography sx={{ fontSize: 19, fontWeight: 700 }}>Предсказанный класс: {result.predicted_class}</Typography>
      <Typography sx={{ mb: 1.5 }}>Уверенность: {(result.predicted_probability * 100).toFixed(1)}%</Typography>
      <Table size="small" aria-label="Вероятности классов"><TableHead><TableRow><TableCell>Класс</TableCell><TableCell align="right">Вероятность</TableCell></TableRow></TableHead>
        <TableBody>{Object.entries(result.probabilities).sort((a, b) => b[1] - a[1]).map(([label, probability]) => <TableRow key={label}><TableCell>{label}</TableCell><TableCell align="right">{(probability * 100).toFixed(2)}%</TableCell></TableRow>)}</TableBody>
      </Table>
      <Box sx={{ mt: 1, fontSize: 12, color: "text.secondary" }}>Вероятности получены из predict_proba финального pipeline; это не оценка точности на независимой выборке.</Box>
    </section>}
  </>;
}
