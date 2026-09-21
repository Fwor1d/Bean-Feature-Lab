import { Alert, Button, Typography } from "@mui/material";
import Link from "@/components/ClientLink";
import { api, apiErrorMessage } from "@/lib/api/client";

export default async function ComparePage() {
  let error: string | null = null;
  try { await api.runs(); } catch (caught) { error = apiErrorMessage(caught); }
  return <>
    <h1 className="page-heading">Сравнение</h1>
    <p className="page-question">Сопоставление моделей и бюджетов допускается только при проверенных одинаковых условиях: dataset version, outer splits и протокол.</p>
    {error && <Alert severity="warning" sx={{ mb: 2 }}>{error}</Alert>}
    <section className="section-surface" aria-labelledby="comparison-title">
      <h2 id="comparison-title" style={{ marginTop: 0, fontSize: 17 }}>Сопоставимые запуски</h2>
      <Typography color="text.secondary" sx={{ mb: 2 }}>Нечего сравнивать: рассчитанных запусков пока нет.</Typography>
      <Button component={Link} href="/runs" variant="outlined">Открыть журнал запусков</Button>
    </section>
    <p style={{ color: "#647283", fontSize: 13 }}>Победитель и минимально достаточное k не определены.</p>
  </>;
}
