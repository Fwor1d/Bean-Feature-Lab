import { Alert, Chip } from "@mui/material";
import { api, apiErrorMessage } from "@/lib/api/client";

export default async function SettingsPage() {
  let info: Awaited<ReturnType<typeof api.systemInfo>> | null = null;
  let error: string | null = null;
  try { info = await api.systemInfo(); } catch (caught) { error = apiErrorMessage(caught); }
  return <>
    <h1 className="page-heading">Настройки проекта</h1>
    <p className="page-question">Локальная среда и связь с backend. Полные локальные пути и чувствительные параметры здесь не выводятся.</p>
    {error && <Alert severity="warning" sx={{ mb: 2 }}>{error}</Alert>}
    <section className="section-surface" aria-labelledby="system-title">
      <h2 id="system-title" style={{ marginTop: 0, fontSize: 17 }}>Состояние системы</h2>
      <div className="status-line"><strong>API</strong><Chip label={info ? `v${info.app_version}` : "Недоступен"} size="small" variant="outlined" /></div>
      <hr className="section-rule" /><div className="status-line"><strong>SQLite</strong><span>{info?.database === "connected" ? "Подключено" : "Нет соединения"}</span></div>
      <hr className="section-rule" /><div className="status-line"><strong>Worker</strong><span>{info?.worker === "online" ? "Работает" : info?.worker === "offline" ? "Не отвечает" : "Не запущен"}</span></div>
      <hr className="section-rule" /><div className="status-line"><strong>Python</strong><span>{info?.python_version ?? "—"}</span><strong>Платформа</strong><span>{info?.platform ?? "—"}</span></div>
      <hr className="section-rule" /><div className="status-line"><strong>Git commit</strong><span style={{ fontFamily: "monospace" }}>{info?.git_commit ?? "Недоступно"}</span></div>
    </section>
  </>;
}
