"use client";

import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { Button, Divider, FormControl, InputLabel, MenuItem, Select, Typography } from "@mui/material";
import { IconArrowRight, IconInfoCircle } from "@tabler/icons-react";

const contextCopy: Record<string, { heading: string; groups: { label: string; text: string }[] }> = {
  "/": { heading: "Состояние проекта", groups: [
    { label: "Источник", text: "Основной источник — UCI Dry Bean Dataset, ID 602. Данные пока не загружены." },
    { label: "Результаты", text: "Эксперименты не выполнялись. Научные показатели отсутствуют." },
  ] },
  "/experiments": { heading: "Конфигурация", groups: [
    { label: "Конфигурация → запуск", text: "Конфигурация задаёт условия; каждый запуск получает отдельный ID и статус." },
    { label: "На этом этапе", text: "Можно создать определение через API или CLI. Исполнитель ML пока не подключён." },
  ] },
  "/runs": { heading: "Исполнение", groups: [
    { label: "Очередь", text: "Локальный worker видит сохранённые задания, но не выполняет обучение на этом этапе." },
    { label: "Результат", text: "QUEUED не означает наличие рассчитанных метрик." },
  ] },
  "/features": { heading: "Признаки", groups: [
    { label: "Исходные измерения", text: "Набор исходных признаков появится только после настоящего запуска отбора." },
    { label: "PCA", text: "Компоненты не равны физически измеряемым исходным признакам." },
  ] },
  "/compare": { heading: "Условия сравнения", groups: [
    { label: "Сопоставимость", text: "Сравнивать можно runs с одинаковой версией данных и внешними CV-разбиениями." },
    { label: "Сейчас", text: "Расчётов для сравнения нет." },
  ] },
  "/classifier": { heading: "Применение модели", groups: [
    { label: "Реестр моделей", text: "Проверенные модели пока не обучены и не зарегистрированы." },
    { label: "Граница", text: "Предсказание в будущем не будет подменять оценку качества в experiment run." },
  ] },
  "/settings": { heading: "Локальная среда", groups: [
    { label: "Конфигурация", text: "Параметры подключения задаются локальными environment variables." },
    { label: "Хранилище", text: "SQLite хранит metadata, dataset и артефакты хранятся отдельно." },
  ] },
};

function BudgetContext() {
  const router = useRouter();
  const search = useSearchParams();
  const budget = search.get("budget") === "pca_components" ? "pca_components" : "original_features";
  const selector = search.get("selector") ?? "mutual_information";
  const model = search.get("model") ?? "all";
  const setParam = (key: string, value: string) => {
    const params = new URLSearchParams(search.toString());
    params.set(key, value);
    if (key === "budget") params.set("selector", value === "pca_components" ? "pca" : "mutual_information");
    router.replace(`/feature-budget?${params.toString()}`);
  };
  return (
    <>
      <h2 className="context-heading">Контекст и параметры</h2>
      <div className="context-group">
        <p className="context-label">Тип бюджета</p>
        <FormControl fullWidth size="small" sx={{ "& .MuiOutlinedInput-root": { color: "#fff" }, "& fieldset": { borderColor: "#63717f" }, "& .MuiSvgIcon-root": { color: "#fff" } }}>
          <InputLabel id="budget-kind-label" sx={{ color: "#d4dee7" }}>Представление</InputLabel>
          <Select labelId="budget-kind-label" label="Представление" value={budget} onChange={event => setParam("budget", event.target.value)}>
            <MenuItem value="original_features">Исходные признаки</MenuItem><MenuItem value="pca_components">Компоненты PCA</MenuItem>
          </Select>
        </FormControl>
        <p className="context-copy">{budget === "pca_components" ? "Компоненты PCA требуют исходные измерения; это не бюджет физических признаков." : "k означает число исходных измеряемых признаков."}</p>
      </div>
      <div className="context-group">
        <p className="context-label">Метод отбора · фильтр результатов</p>
        <FormControl fullWidth size="small" disabled sx={{ "& .MuiOutlinedInput-root": { color: "#fff" }, "& fieldset": { borderColor: "#63717f" }, "& .MuiSvgIcon-root": { color: "#fff" } }}>
          <InputLabel id="selector-label" sx={{ color: "#d4dee7" }}>Метод</InputLabel>
          <Select labelId="selector-label" label="Метод" value={budget === "pca_components" ? "pca" : selector} disabled={budget === "pca_components"} onChange={event => setParam("selector", event.target.value)}>
            <MenuItem value="mutual_information">Mutual Information</MenuItem><MenuItem value="anova">ANOVA</MenuItem><MenuItem value="rfe">RFE</MenuItem><MenuItem value="l1_logistic">L1 Logistic</MenuItem><MenuItem value="tree_importance">Tree importance</MenuItem><MenuItem value="pca">PCA</MenuItem>
          </Select>
        </FormControl>
        <p className="context-copy">Недоступен до появления рассчитанных результатов; конфигурацию эксперимента он не меняет.</p>
      </div>
      <div className="context-group">
        <p className="context-label">Классификатор · фильтр результатов</p>
        <FormControl fullWidth size="small" disabled sx={{ "& .MuiOutlinedInput-root": { color: "#fff" }, "& fieldset": { borderColor: "#63717f" }, "& .MuiSvgIcon-root": { color: "#fff" } }}>
          <InputLabel id="model-label" sx={{ color: "#d4dee7" }}>Модель</InputLabel>
          <Select labelId="model-label" label="Модель" value={model} onChange={event => setParam("model", event.target.value)}>
            <MenuItem value="all">Все модели</MenuItem><MenuItem value="logistic_regression">Logistic Regression</MenuItem><MenuItem value="svm_rbf">SVM RBF</MenuItem><MenuItem value="random_forest">Random Forest</MenuItem><MenuItem value="xgboost">XGBoost</MenuItem><MenuItem value="lightgbm">LightGBM</MenuItem><MenuItem value="mlp">MLP</MenuItem>
          </Select>
        </FormControl>
        <p className="context-copy">Недоступен до появления реальных сохранённых результатов.</p>
      </div>
      <div className="context-group">
        <p className="context-label">Критерий достаточности <IconInfoCircle size={15} style={{ verticalAlign: "middle" }} /></p>
        <p className="context-copy">Протокольная допустимая потеря Macro-F1: 0,01 относительно базового варианта той же модели. Вывод невозможен до расчёта парных различий и утверждения метода интервала.</p>
      </div>
      <Button component={Link} href="/experiments" variant="outlined" endIcon={<IconArrowRight size={16} />}
        sx={{ color: "#d9e8ff", borderColor: "#7198d6", width: "100%" }}>Сохранить конфигурацию</Button>
      <p className="context-copy">Научный запуск и расчёт метрик пока недоступны.</p>
    </>
  );
}

export function ContextPanel() {
  const pathname = usePathname();
  if (pathname === "/feature-budget") return <><div className="context-mobile-state">Активный выбор не настроен<br />Проект · не выбран<br />Датасет · не выбран<br />Запуск · не выбран</div><BudgetContext /></>;
  const content = contextCopy[pathname] ?? contextCopy["/"];
  return (
    <>
      <div className="context-mobile-state">Активный выбор не настроен<br />Проект · не выбран<br />Датасет · не выбран<br />Запуск · не выбран</div>
      <h2 className="context-heading">{content.heading}</h2>
      {content.groups.map(group => <div className="context-group" key={group.label}><p className="context-label">{group.label}</p><p className="context-copy">{group.text}</p></div>)}
      <Divider sx={{ borderColor: "#4c5762", mb: 2 }} />
      <Typography sx={{ fontSize: 12, color: "#b8c5d1" }}>Версия foundation · 0.1.0</Typography>
    </>
  );
}
