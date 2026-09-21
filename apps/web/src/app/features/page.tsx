import { Alert, Tab, Tabs, Typography } from "@mui/material";
import { api, apiErrorMessage } from "@/lib/api/client";

export default async function FeaturesPage() {
  let error: string | null = null;
  try { await api.runs(); } catch (caught) { error = apiErrorMessage(caught); }
  return <>
    <h1 className="page-heading">Анализ признаков</h1>
    <p className="page-question">Исходные признаки, частоты отбора и устойчивость будут показаны отдельно от PCA-компонент.</p>
    {error && <Alert severity="warning" sx={{ mb: 2 }}>{error}</Alert>}
    <section className="section-surface" aria-labelledby="feature-explorer-title">
      <h2 id="feature-explorer-title" style={{ marginTop: 0, fontSize: 17 }}>Представления признаков</h2>
      <Tabs value={0} aria-label="Виды анализа признаков" sx={{ borderBottom: "1px solid #d9e0e7", mb: 3 }}><Tab label="Исходные признаки" /><Tab label="Частота отбора" disabled /><Tab label="Устойчивость" disabled /><Tab label="PCA" disabled /></Tabs>
      <Typography sx={{ fontWeight: 600 }}>Нет выбранных признаков</Typography>
      <Typography color="text.secondary" sx={{ mt: 1, fontSize: 13 }}>Список и fold-level сведения появятся только после настоящего отбора на обучающих folds.</Typography>
    </section>
  </>;
}
