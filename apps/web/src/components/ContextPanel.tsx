"use client";

import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { Button, Divider, FormControl, InputLabel, MenuItem, Select, Typography } from "@mui/material";
import { IconArrowRight, IconInfoCircle } from "@tabler/icons-react";
import type { Run } from "@/lib/api/contracts";
import { runLabel } from "@/lib/science";

const contextCopy: Record<string, { heading: string; groups: { label: string; text: string }[] }> = {
  "/": { heading: "Состояние проекта", groups: [
    { label: "Источник", text: "Официальный UCI Dry Bean Dataset, ID 602. Статус проверки и hash показаны в разделе признаков." },
    { label: "Результаты", text: "Только завершённые runs дают научные точки. Отсутствующие k остаются пустыми." },
  ] },
  "/experiments": { heading: "Конфигурация", groups: [
    { label: "Конфигурация → запуск", text: "Конфигурация задаёт условия; каждый запуск получает отдельный ID и статус." },
    { label: "Исполнение", text: "Созданный run попадает в очередь локального worker. Полный протокол может требовать времени." },
  ] },
  "/runs": { heading: "Исполнение", groups: [
    { label: "Очередь", text: "Worker выполняет один run за раз; после всех outer folds сохраняет проверенный artifact." },
    { label: "Результат", text: "QUEUED и RUNNING не означают наличие рассчитанных метрик." },
  ] },
  "/features": { heading: "Признаки", groups: [
    { label: "Исходные измерения", text: "Имена и классы показаны из верифицированного официального ARFF." },
    { label: "PCA", text: "Компоненты не равны физически измеряемым исходным признакам." },
  ] },
  "/compare": { heading: "Условия сравнения", groups: [
    { label: "Сопоставимость", text: "Сравнивать можно runs с одинаковой версией данных и внешними CV-разбиениями." },
    { label: "Решение", text: "Достаточность определяет one-sided Nadeau–Bengio corrected interval с margin 0,01 и Bonferroni-поправкой внутри модели." },
  ] },
  "/classifier": { heading: "Применение модели", groups: [
    { label: "Модель", text: "Активная версия из deployment registry; schema, classes и checksum показаны в основной области." },
    { label: "Dataset", text: "UCI Dry Bean · 602" },
    { label: "Источник конфигурации", text: "Исходный scientific run указан в metadata активной модели." },
    { label: "Режим", text: "Deployment / inference" },
    { label: "Граница", text: "Финальная модель обучена на полном валидированном наборе данных. Это inference-сценарий, а не замена nested-CV оценки качества." },
  ] },
  "/settings": { heading: "Локальная среда", groups: [
    { label: "Конфигурация", text: "Параметры подключения задаются локальными environment variables." },
    { label: "Хранилище", text: "SQLite хранит metadata, dataset и артефакты хранятся отдельно." },
  ] },
};

function BudgetContext() {
  const router = useRouter();
  const search = useSearchParams();
  const budget = search.get("budget") === "pca_components" || search.get("selector") === "pca" ? "pca_components" : "original_features";
  const selector = search.get("selector") ?? "mutual_information";
  const model = search.get("model") ?? "all";
  const setParam = (key: string, value: string) => {
    const params = new URLSearchParams(search.toString());
    params.set(key, value);
    if (key === "budget") params.set("selector", value === "pca_components" ? "pca" : "mutual_information");
    router.push(`/feature-budget?${params.toString()}`);
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
        <FormControl fullWidth size="small" sx={{ "& .MuiOutlinedInput-root": { color: "#fff" }, "& fieldset": { borderColor: "#63717f" }, "& .MuiSvgIcon-root": { color: "#fff" } }}>
          <InputLabel id="selector-label" sx={{ color: "#d4dee7" }}>Метод</InputLabel>
          <Select labelId="selector-label" label="Метод" value={budget === "pca_components" ? "pca" : selector} disabled={budget === "pca_components"} onChange={event => setParam("selector", event.target.value)}>
            <MenuItem value="mutual_information">Mutual Information</MenuItem><MenuItem value="anova">ANOVA</MenuItem><MenuItem value="rfe">RFE</MenuItem><MenuItem value="l1_logistic">L1 Logistic</MenuItem><MenuItem value="tree_importance">Tree importance</MenuItem>{budget === "pca_components" && <MenuItem value="pca">PCA</MenuItem>}
          </Select>
        </FormControl>
        <p className="context-copy">Фильтр показывает только реальные завершённые conditions. Comparator-методы используют заранее утверждённые контрольные точки; отсутствующие точки не интерполируются.</p>
      </div>
      <div className="context-group">
        <p className="context-label">Классификатор · фильтр результатов</p>
        <FormControl fullWidth size="small" sx={{ "& .MuiOutlinedInput-root": { color: "#fff" }, "& fieldset": { borderColor: "#63717f" }, "& .MuiSvgIcon-root": { color: "#fff" } }}>
          <InputLabel id="model-label" sx={{ color: "#d4dee7" }}>Модель</InputLabel>
          <Select labelId="model-label" label="Модель" value={model} onChange={event => setParam("model", event.target.value)}>
            <MenuItem value="all">Все модели</MenuItem><MenuItem value="logistic_regression">Logistic Regression</MenuItem><MenuItem value="svm_rbf">SVM RBF</MenuItem><MenuItem value="random_forest">Random Forest</MenuItem><MenuItem value="xgboost">XGBoost</MenuItem><MenuItem value="lightgbm">LightGBM</MenuItem><MenuItem value="mlp">MLP</MenuItem>
          </Select>
        </FormControl>
        <p className="context-copy">Модель фильтрует только реально завершённые условия.</p>
      </div>
      <div className="context-group">
        <p className="context-label">Критерий достаточности <IconInfoCircle size={15} style={{ verticalAlign: "middle" }} /></p>
        <p className="context-copy">Допустимая потеря Macro-F1: 0,01. Односторонняя верхняя граница считается Nadeau–Bengio corrected method с Bonferroni α=0,05/15.</p>
      </div>
      <Button component={Link} href="/experiments" variant="outlined" endIcon={<IconArrowRight size={16} />}
        sx={{ color: "#d9e8ff", borderColor: "#7198d6", width: "100%" }}>К реестру конфигураций</Button>
      <p className="context-copy">Сохранённую конфигурацию запускает worker; анализ не изменяет научные условия.</p>
    </>
  );
}

export function ContextPanel({ runs }: { runs: Run[] | null }) {
  const pathname = usePathname();
  if (pathname === "/feature-budget") return <><BudgetContext /></>;
  const runId = pathname.match(/^\/runs\/(\d+)$/)?.[1];
  const selectedRun = runs?.find(run => run.id === Number(runId));
  if (runId) return <>
    <h2 className="context-heading">Контекст запуска</h2>
    <div className="context-group"><p className="context-label">Запись</p><p className="context-copy">{selectedRun?.display_id ?? `Run #${runId}`} · {selectedRun ? runLabel[selectedRun.status] : "Не удалось загрузить статус"}</p></div>
    <div className="context-group"><p className="context-label">Научный результат</p><p className="context-copy">{selectedRun?.result_state === "CALCULATED" ? "Сводка и folds построены из проверенного результата. Хеш и происхождение доступны в основной области." : "Не рассчитано: метрики не публикуются до завершения и проверки artifact."}</p></div>
    <div className="context-group"><p className="context-label">Воспроизводимость</p><p className="context-copy">Проверьте dataset SHA-256, Git, outer split set и параметры внутреннего поиска в деталях запуска.</p></div>
    <Button component={Link} href="/compare" variant="outlined" sx={{ color: "#d9e8ff", borderColor: "#7198d6", width: "100%" }}>Перейти к сравнению</Button>
  </>;
  const content = pathname.startsWith("/runs/") ? contextCopy["/runs"] : contextCopy[pathname] ?? contextCopy["/"];
  return (
    <>
      <h2 className="context-heading">{content.heading}</h2>
      {content.groups.map(group => <div className="context-group" key={group.label}><p className="context-label">{group.label}</p><p className="context-copy">{group.text}</p></div>)}
      <Divider sx={{ borderColor: "#4c5762", mb: 2 }} />
      <Typography sx={{ fontSize: 12, color: "#b8c5d1" }}>BeanFeature Lab · локальный научный инструмент</Typography>
    </>
  );
}
