import { Alert, Chip } from "@mui/material";
import { EmptyPlot } from "@/components/EmptyPlot";
import { EmptyResultsGrid } from "@/components/EmptyResultsGrid";
import { api, apiErrorMessage } from "@/lib/api/client";

export default async function FeatureBudgetPage({ searchParams }: { searchParams: Promise<{ budget?: string }> }) {
  const { budget } = await searchParams;
  const pca = budget === "pca_components";
  let apiError: string | null = null;
  let runsCount: number | null = null;
  try { runsCount = (await api.runs()).length; } catch (error) { apiError = apiErrorMessage(error); }
  return (
    <>
      <h1 className="page-heading">Бюджет признаков</h1>
      <p className="page-question">Как меняется качество классификации при сокращении числа {pca ? "компонент PCA" : "исходных измеряемых признаков"}? Научный вывод появится только после воспроизводимого запуска.</p>
      {apiError && <Alert severity="warning" sx={{ mb: 2 }}>{apiError} <a href="/feature-budget">Повторить запрос</a></Alert>}
      {runsCount !== null && runsCount > 0 && <p className="page-question">В хранилище зарегистрировано запусков: {runsCount}. Выбор запуска и научные результаты на этом этапе недоступны.</p>}
      <section className="figure-surface" aria-labelledby="figure-title">
        <div className="figure-heading">
          <h2 id="figure-title">Качество модели в зависимости от {pca ? "числа компонент" : "бюджета признаков"}</h2>
          <Chip label="Не рассчитано" size="small" variant="outlined" sx={{ color: "#526478", borderColor: "#a9b5c0" }} />
        </div>
        <EmptyPlot pca={pca} />
        <p className="table-note" style={{ margin: "0 0 6px 46px" }}>{pca ? "PCA: компоненты нового представления; для их вычисления нужны 16 исходных измерений." : "Исходные признаки: k = 1…16. Ось — условие протокола, не измеренный результат."}</p>
      </section>
      <section className="table-surface" aria-labelledby="table-title">
        <div className="table-heading"><h2 id="table-title">{pca ? "Компоненты и условия" : "Выбранные признаки и результаты"}</h2><span className="table-note">Нет записей по разбиениям</span></div>
        <EmptyResultsGrid pca={pca} />
      </section>
    </>
  );
}
