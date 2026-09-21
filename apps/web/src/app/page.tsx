import Link from "@/components/ClientLink";
import { Alert, Button, Chip } from "@mui/material";
import { IconArrowRight, IconDatabase, IconFlask, IconPlayerPlay } from "@tabler/icons-react";
import { api, apiErrorMessage } from "@/lib/api/client";

export default async function HomePage() {
  let status = "API недоступен";
  let experiments = 0;
  let runs = 0;
  let error: string | null = null;
  try {
    const [system, experimentList, runList] = await Promise.all([api.systemInfo(), api.experiments(), api.runs()]);
    status = system.database === "connected" ? "Подключено" : "Хранилище недоступно";
    experiments = experimentList.length;
    runs = runList.length;
  } catch (caught) { error = apiErrorMessage(caught); }
  return <>
    <h1 className="page-heading">Состояние исследования</h1>
    <p className="page-question">Рабочее пространство для изучения влияния числа морфологических признаков на классификацию сортов фасоли.</p>
    {error && <Alert severity="warning" sx={{ mb: 2 }}>{error}</Alert>}
    <section className="section-surface" aria-labelledby="overview-title">
      <h2 id="overview-title" style={{ marginTop: 0, fontSize: 18 }}>Текущая контрольная точка</h2>
      <div className="status-line"><Chip label={`API · ${status}`} size="small" variant="outlined" /><Chip label="Научные результаты · Не рассчитано" size="small" variant="outlined" /></div>
      <hr className="section-rule" />
      <div className="status-line"><IconDatabase size={20} /><strong>Датасет</strong><span>UCI Dry Bean, ID 602 · не загружен</span></div>
      <hr className="section-rule" />
      <div className="status-line"><IconFlask size={20} /><strong>Конфигурации</strong><span>{experiments === 0 ? "Не созданы" : `${experiments} сохранено`}</span><Button component={Link} href="/experiments" size="small" endIcon={<IconArrowRight size={15} />}>Открыть</Button></div>
      <hr className="section-rule" />
      <div className="status-line"><IconPlayerPlay size={20} /><strong>Запуски</strong><span>{runs === 0 ? "Не запускались" : `${runs} в журнале`}</span><Button component={Link} href="/runs" size="small" endIcon={<IconArrowRight size={15} />}>Журнал</Button></div>
    </section>
    <p style={{ marginTop: 20, color: "#526170", fontSize: 13 }}>Следующий этап — загрузка и проверка официального датасета, затем реализация научного исполнителя по утверждённому протоколу.</p>
  </>;
}
