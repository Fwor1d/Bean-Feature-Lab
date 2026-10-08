"use client";

import { useRef, useState } from "react";
import { Alert, Box, Button, CircularProgress, Stack, Table, TableBody, TableCell, TableContainer, TableHead, TableRow, TextField, Typography } from "@mui/material";
import { api, apiErrorMessage } from "@/lib/api/client";
import type { ClassifierExample, ClassifierModel, ClassifierPrediction } from "@/lib/api/contracts";

type HistoryItem = {
  id: number;
  timestamp: string;
  predicted: string;
  confidence: number;
  source: "Вручную" | "Пример UCI";
  actual: string | null;
};

export function ClassifierForm({ model }: { model: ClassifierModel }) {
  const [values, setValues] = useState<Record<string, string>>({});
  const [result, setResult] = useState<ClassifierPrediction | null>(null);
  const [example, setExample] = useState<ClassifierExample | null>(null);
  const [history, setHistory] = useState<HistoryItem[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [invalidField, setInvalidField] = useState<string | null>(null);
  const inputs = useRef<Record<string, HTMLInputElement | null>>({});

  async function fillExample() {
    setBusy(true); setError(null); setResult(null); setInvalidField(null);
    try {
      const example = await api.classifierExample();
      setValues(Object.fromEntries(model.feature_names.map(name => [name, String(example.features[name])])));
      setExample(example);
    } catch (caught) { setError(apiErrorMessage(caught)); }
    finally { setBusy(false); }
  }

  async function predict() {
    const features: Record<string, number> = {};
    for (const name of model.feature_names) {
      const raw = values[name]?.trim();
      if (!raw || !Number.isFinite(Number(raw))) {
        setError(`Введите конечное числовое значение для ${name}.`);
        setInvalidField(name); inputs.current[name]?.focus(); setResult(null);
        return;
      }
      features[name] = Number(raw);
    }
    setBusy(true); setError(null); setResult(null); setInvalidField(null);
    try {
      const prediction = await api.predict(features);
      setResult(prediction);
      const historyItem: HistoryItem = {
        id: Date.now(), timestamp: new Date().toLocaleTimeString("ru-RU"),
        predicted: prediction.predicted_class, confidence: prediction.predicted_probability,
        source: example ? "Пример UCI" : "Вручную", actual: example?.actual_class ?? null,
      };
      setHistory(previous => [historyItem, ...previous].slice(0, 10));
    }
    catch (caught) { setError(apiErrorMessage(caught)); }
    finally { setBusy(false); }
  }

  return <>
    <section className="section-surface" aria-labelledby="prediction-title">
      <h2 id="prediction-title" style={{ marginTop: 0, fontSize: 17 }}>Табличный ввод</h2>
      <Typography color="text.secondary" sx={{ mb: 1.5, fontSize: 13 }}>16 канонических признаков UCI · {model.model_family} · {model.source_run}. «Заполнить пример» берёт реальную строку из проверенного датасета.</Typography>
      <TableContainer sx={{ maxHeight: 445, border: "1px solid", borderColor: "divider" }}>
        <Table stickyHeader size="small" aria-label="Входные признаки фасоли">
          <TableHead><TableRow><TableCell>Признак UCI</TableCell><TableCell>Значение</TableCell><TableCell align="right">Наблюдаемый диапазон</TableCell></TableRow></TableHead>
          <TableBody>{model.feature_names.map(name => <TableRow key={name}>
            <TableCell sx={{ fontFamily: "monospace", fontSize: 12 }}>{name}</TableCell>
            <TableCell><TextField id={`classifier-${name}`} inputRef={(element: HTMLInputElement | null) => { inputs.current[name] = element; }} error={invalidField === name} helperText={invalidField === name ? "Введите конечное число" : undefined} disabled={busy} size="small" type="number" fullWidth value={values[name] ?? ""} onChange={event => { setValues(previous => ({ ...previous, [name]: event.target.value })); setExample(null); setResult(null); setError(null); setInvalidField(null); }} slotProps={{ htmlInput: { step: "any", "aria-label": name } }} /></TableCell>
            <TableCell align="right" sx={{ color: "text.secondary", whiteSpace: "nowrap", fontSize: 12 }}>{model.observed_ranges?.[name] ? `${model.observed_ranges[name].minimum.toLocaleString("ru-RU")} … ${model.observed_ranges[name].maximum.toLocaleString("ru-RU")}` : "—"}</TableCell>
          </TableRow>)}</TableBody>
        </Table>
      </TableContainer>
      <Stack direction="row" spacing={1} sx={{ mt: 2, flexWrap: "wrap", gap: 1 }}>
        <Button variant="contained" onClick={predict} disabled={busy}>{busy ? <><CircularProgress size={18} color="inherit" aria-hidden /> Вычисляем прогноз…</> : "Предсказать"}</Button>
        <Button variant="outlined" onClick={fillExample} disabled={busy}>Заполнить пример</Button>
        <Button variant="text" onClick={() => { setValues({}); setResult(null); setExample(null); setError(null); setInvalidField(null); }} disabled={busy}>Очистить</Button>
      </Stack>
      {error && <Alert severity="error" sx={{ mt: 2 }}>{error}</Alert>}
    </section>
    {result && <section className="section-surface" aria-live="polite" style={{ marginTop: 16 }}>
      <h2 style={{ marginTop: 0, fontSize: 17 }}>Результат предсказания</h2>
      <Typography sx={{ fontSize: 19, fontWeight: 700 }}>Предсказанный класс: {result.predicted_class}</Typography>
      <Typography sx={{ mb: 1.5 }}>Вероятность предсказанного класса: {(result.predicted_probability * 100).toFixed(1)}%</Typography>
      {example && <Alert severity={result.predicted_class === example.actual_class ? "success" : "warning"} sx={{ mb: 1.5 }}>Реальный класс строки UCI №{example.row_index + 1}: {example.actual_class}. {result.predicted_class === example.actual_class ? "Прогноз совпал." : "Прогноз не совпал."} Это один demo-объект, не новая метрика.</Alert>}
      <Table size="small" aria-label="Вероятности классов"><TableHead><TableRow><TableCell>Класс</TableCell><TableCell align="right">Вероятность</TableCell></TableRow></TableHead>
        <TableBody>{Object.entries(result.probabilities).sort((a, b) => b[1] - a[1]).map(([label, probability]) => <TableRow key={label}><TableCell>{label}</TableCell><TableCell align="right">{(probability * 100).toFixed(2)}%</TableCell></TableRow>)}</TableBody>
      </Table>
      <Box sx={{ mt: 1, fontSize: 12, color: "text.secondary" }}>Вероятности получены из predict_proba финального pipeline; это не оценка точности на независимой выборке. Вероятности не проходили отдельную калибровку.</Box>
      {result.local_explanation && <Box sx={{ mt: 2 }}>
        <Typography component="h3" sx={{ fontSize: 15, fontWeight: 700, mb: 0.5 }}>Локальные вклады в logit класса {result.local_explanation.target_class}</Typography>
        <TableContainer><Table size="small" aria-label="Локальные вклады Logistic Regression"><TableHead><TableRow><TableCell>Признак</TableCell><TableCell align="right">Стандартизованное значение</TableCell><TableCell align="right">Коэффициент</TableCell><TableCell align="right">Вклад в logit</TableCell></TableRow></TableHead><TableBody>{result.local_explanation.contributions.map(item => <TableRow key={item.feature}><TableCell>{item.feature}</TableCell><TableCell align="right">{item.standardized_value.toFixed(3)}</TableCell><TableCell align="right">{item.coefficient.toFixed(4)}</TableCell><TableCell align="right">{item.logit_contribution.toFixed(4)}</TableCell></TableRow>)}</TableBody></Table></TableContainer>
        <Box sx={{ mt: 1, fontSize: 12, color: "text.secondary" }}>Знак и величина показывают вклад только в линейный logit предсказанного класса после fitted scaling. Это локальное математическое разложение, не causal и не global importance; сумма вкладов не является вероятностью.</Box>
      </Box>}
    </section>}
    {history.length > 0 && <section className="table-surface" style={{ marginTop: 16 }} aria-labelledby="history-title">
      <div className="table-heading"><h2 id="history-title">История текущей сессии</h2><span className="table-note">Только в памяти браузера · не scientific database</span></div>
      <Table size="small"><TableHead><TableRow><TableCell>Время</TableCell><TableCell>Источник</TableCell><TableCell>Прогноз</TableCell><TableCell align="right">Вероятность</TableCell><TableCell>Реальный класс</TableCell></TableRow></TableHead><TableBody>{history.map(item => <TableRow key={item.id}><TableCell>{item.timestamp}</TableCell><TableCell>{item.source}</TableCell><TableCell>{item.predicted}</TableCell><TableCell align="right">{(item.confidence * 100).toFixed(1)}%</TableCell><TableCell>{item.actual ?? "—"}</TableCell></TableRow>)}</TableBody></Table>
    </section>}
  </>;
}
