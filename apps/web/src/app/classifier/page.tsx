import { Alert } from "@mui/material";
import { api, apiErrorMessage } from "@/lib/api/client";
import { ClassifierForm } from "./ClassifierForm";

export default async function ClassifierPage() {
  let model: Awaited<ReturnType<typeof api.classifierModel>> | null = null;
  let error: string | null = null;
  try { model = await api.classifierModel(); } catch (caught) { error = apiErrorMessage(caught); }
  return <>
    <h1 className="page-heading">Классификатор</h1>
    <p className="page-question">Применение финальной модели к табличным данным — отдельный inference-сценарий, не экспериментальная оценка.</p>
    {model ? <ClassifierForm model={model} /> : <Alert severity="warning">{error} Модель не зарегистрирована; выполните <code>beanfeature classifier train</code>.</Alert>}
  </>;
}
