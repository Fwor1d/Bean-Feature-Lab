import { Alert, Button, TextField, Typography } from "@mui/material";

export default function ClassifierPage() {
  return <>
    <h1 className="page-heading">Классификатор</h1>
    <p className="page-question">Применение проверенной зарегистрированной модели к валидным табличным данным — отдельный сценарий, не экспериментальная оценка.</p>
    <Alert severity="info" sx={{ mb: 2 }}>Модель не зарегистрирована. Предсказание недоступно до обучения и проверки научного pipeline.</Alert>
    <section className="section-surface" aria-labelledby="prediction-title">
      <h2 id="prediction-title" style={{ marginTop: 0, fontSize: 17 }}>Табличный ввод</h2>
      <Typography color="text.secondary" sx={{ mb: 2, fontSize: 13 }}>После регистрации модели здесь появится форма её входных признаков и версия схемы.</Typography>
      <TextField label="Версия модели" disabled value="Нет модели" sx={{ mr: 2, mb: 1 }} />
      <Button variant="contained" disabled>Предсказать</Button>
    </section>
  </>;
}
