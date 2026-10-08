import { Alert } from "@mui/material";
import { api, apiErrorMessage } from "@/lib/api/client";
import { ExperimentRegister } from "@/components/ExperimentRegister";

export default async function ExperimentsPage() {
  let experiments: Awaited<ReturnType<typeof api.experiments>> = [];
  let datasets: Awaited<ReturnType<typeof api.datasets>> = [];
  let runs: Awaited<ReturnType<typeof api.runs>> = [];
  let error: string | null = null;
  try { [experiments, datasets, runs] = await Promise.all([api.experiments(), api.datasets(), api.runs()]); } catch (caught) { error = apiErrorMessage(caught); }
  return <>
    <h1 className="page-heading">Эксперименты</h1>
    <p className="page-question">Определение эксперимента хранит условия исследования. Запуск — отдельная запись исполнения с собственным статусом.</p>
    {error && <Alert severity="warning" sx={{ mb: 2 }}>{error}</Alert>}
    <ExperimentRegister initialExperiments={experiments} initialRuns={runs} datasetVersion={datasets[0]?.version ?? null} />
  </>;
}
