import { Alert, Chip } from "@mui/material";
import { api, apiErrorMessage } from "@/lib/api/client";

const runLabels: Record<string, string> = { DRAFT: "Черновик", QUEUED: "В очереди", RUNNING: "Выполняется", COMPLETED: "Завершён", FAILED: "Ошибка", CANCELLED: "Отменён" };

export default async function RunsPage() {
  let runs: Awaited<ReturnType<typeof api.runs>> = [];
  let error: string | null = null;
  try { runs = await api.runs(); } catch (caught) { error = apiErrorMessage(caught); }
  return <>
    <h1 className="page-heading">Запуски</h1>
    <p className="page-question">Журнал исполнений отделён от реестра конфигураций. Состояние запуска не является научным результатом.</p>
    {error && <Alert severity="warning" sx={{ mb: 2 }}>{error}</Alert>}
    <section className="section-surface" aria-labelledby="runs-title">
      <h2 id="runs-title" style={{ marginTop: 0, fontSize: 17 }}>Очередь и история</h2>
      {runs.length === 0 ? <><p>Запусков пока нет.</p><p style={{ color: "#576778", fontSize: 13 }}>После создания конфигурации её можно поставить в очередь через API или CLI. На этапе 4A worker не обучает модели.</p></> :
        <div style={{ overflowX: "auto" }}><table style={{ borderCollapse: "collapse", width: "100%", minWidth: 540, fontSize: 13 }}><thead><tr><th style={{ textAlign: "left", padding: 10 }}>Run ID</th><th style={{ textAlign: "left", padding: 10 }}>Конфигурация</th><th style={{ textAlign: "left", padding: 10 }}>Статус</th><th style={{ textAlign: "left", padding: 10 }}>Научный результат</th></tr></thead><tbody>
          {runs.map(run => <tr key={run.id} style={{ borderTop: "1px solid #dce3ea" }}><td style={{ padding: 10, fontFamily: "monospace" }}>{run.display_id}</td><td style={{ padding: 10 }}>#{run.experiment_id}</td><td style={{ padding: 10 }}><Chip label={runLabels[run.status]} size="small" variant="outlined" /></td><td style={{ padding: 10 }}>Не рассчитано</td></tr>)}
        </tbody></table></div>}
    </section>
  </>;
}
