"use client";

import { useCallback, useEffect, useRef, useState, useSyncExternalStore } from "react";
import dynamic from "next/dynamic";
import Link from "next/link";
import { Alert, Button, FormControl, InputLabel, MenuItem, Select } from "@mui/material";
import { IconArrowLeft, IconArrowRight, IconArrowsMaximize, IconDownload } from "@tabler/icons-react";
import type { Data } from "plotly.js";
import type { ModelId, SelectorId } from "@/lib/api/contracts";
import { acceptsNavigation, presentationStep, reportPoints, reportRequest, reportPDF, ReportRequestError, type CoreSnapshot, type ReportCohort } from "@/lib/api/reporting";
import { metric, modelLabel, selectorLabel, utcTime } from "@/lib/science";
import { ScientificPlot } from "./ScientificPlot";
import styles from "./Conference.module.css";
import { ConferenceStatus } from "./ConferenceStatus";

const Plot = dynamic(() => import("react-plotly.js"), { ssr: false });
const steps = ["Вопрос", "Данные", "Протокол", "Бюджет", "Sufficient-k", "Методы", "Ограничения", "Источники"];
const titles = ["Сколько признаков достаточно?", "Один dataset. Семь классов.", "Качество всей процедуры, а не подогнанной модели", "Как меняется Macro-F1 при сокращении бюджета", "Достаточное k — в рамках заданного протокола", "Отбор признаков и размерность — разные задачи", "Что позволяют утверждать эти результаты", "От результата к воспроизводимому свидетельству"];
const subscribe = (callback: () => void) => { window.addEventListener("hashchange", callback); window.addEventListener("popstate", callback); return () => { window.removeEventListener("hashchange", callback); window.removeEventListener("popstate", callback); }; };
const getStep = () => presentationStep(window.location.hash);

export function Conference() {
  const step = useSyncExternalStore(subscribe, getStep, () => 0);
  const [snapshot, setSnapshot] = useState<CoreSnapshot | null>(null);
  const [cohorts, setCohorts] = useState<ReportCohort[]>([]);
  const [cohort, setCohort] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [expired, setExpired] = useState(false);
  const [exporting, setExporting] = useState(false);
  const [pdfError, setPDFError] = useState("");
  const [fullscreenError, setFullscreenError] = useState("");
  const [selector, setSelector] = useState<SelectorId>("anova");
  const [closeup, setCloseup] = useState(true);
  const [model, setModel] = useState<ModelId>("logistic_regression");
  const stage = useRef<HTMLDivElement>(null);
  const heading = useRef<HTMLHeadingElement>(null);
  const navigate = useCallback((next: number) => {
    window.history.pushState(null, "", `#step=${Math.max(0, Math.min(7, next)) + 1}`);
    window.dispatchEvent(new Event("hashchange"));
    heading.current?.focus({ preventScroll: true });
    window.scrollTo({ top: 0, behavior: "instant" });
  }, []);
  const load = useCallback(async (id: string) => {
    setLoading(true); setError(""); setPDFError("");
    try {
      const value = await reportRequest<CoreSnapshot>(`snapshot?cohort_id=${id}`);
      setSnapshot(value); setExpired(false); setCohort(id);
    } catch (e) { setError(e instanceof Error ? e.message : "API недоступен."); }
    finally { setLoading(false); }
  }, []);
  useEffect(() => {
    let alive = true;
    reportRequest<ReportCohort[]>("cohorts").then(async rows => {
      if (!alive) return;
      setCohorts(rows);
      if (rows.length === 1) await load(rows[0].cohort_id);
      else { setLoading(false); if (!rows.length) setError("Проверенных full-protocol результатов пока нет. Снимок не рассчитан."); }
    }).catch(e => { if (alive) { setError(e.message); setLoading(false); } });
    return () => { alive = false; };
  }, [load]);
  useEffect(() => {
    const handler = (event: KeyboardEvent) => {
      if (!acceptsNavigation(event, event.target as HTMLElement)) return;
      event.preventDefault();
      navigate(event.key === "Home" ? 0 : event.key === "End" ? 7 : step + (event.key === "ArrowRight" ? 1 : -1));
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [step, navigate]);
  useEffect(() => {
    if (!snapshot) return;
    const timer = window.setInterval(() => {
      if (Date.now() >= Date.parse(snapshot.expires_at_utc)) setExpired(true);
      else reportRequest(`/${snapshot.snapshot_id}/evidence`.replace(/^\//, "")).catch(e => { if (e instanceof ReportRequestError && e.code === "snapshot_expired") setExpired(true); });
    }, 60_000);
    return () => window.clearInterval(timer);
  }, [snapshot]);
  const downloadPDF = async () => {
    if (!snapshot || exporting || expired) return;
    setExporting(true); setPDFError("");
    try {
      const { blob, filename } = await reportPDF(snapshot);
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url; link.download = filename;
      document.body.appendChild(link); link.click(); link.remove();
      window.setTimeout(() => URL.revokeObjectURL(url), 1000);
    } catch (e) {
      if (e instanceof ReportRequestError && e.code === "snapshot_expired") setExpired(true);
      setPDFError(e instanceof Error ? e.message : "Не удалось скачать PDF.");
    } finally { setExporting(false); }
  };
  const full = async () => {
    try { if (document.fullscreenElement) await document.exitFullscreen(); else await stage.current?.requestFullscreen(); }
    catch { setFullscreenError("Браузер не разрешил fullscreen. Доклад доступен в обычном окне."); }
  };
  const baselines = snapshot?.runs.filter(r => r.configuration.selector === "none" && r.configuration.k_original_features === 16) ?? [];
  const mi = snapshot ? reportPoints(snapshot, "mutual_information") : [];
  const families = snapshot?.sufficiency ?? [];
  const family = families.find(f => f.model === model);
  const complete = families.every(f => f.status === "CALCULATED");
  const comparisonPoints = snapshot ? reportPoints(snapshot, selector) : [];
  const allUpperPoints = family?.comparisons.filter(c => c.one_sided_upper_confidence_bound != null) ?? [];
  const upperPoints = allUpperPoints.filter(c => !closeup || c.k_original_features >= 10);
  const upperValues = upperPoints.map(c => c.one_sided_upper_confidence_bound!);
  const lower = Math.min(snapshot?.protocol.margin ?? 0.01, ...upperValues);
  const upper = Math.max(snapshot?.protocol.margin ?? 0.01, ...upperValues);
  const padding = Math.max((upper - lower) * 0.15, 0.001);
  const boundTraces: Data[] = [{ type: "scatter", mode: family?.status === "CALCULATED" ? "lines+markers" : "markers", name: "Верхняя граница потери", x: upperPoints.map(c => c.k_original_features), y: upperPoints.map(c => c.one_sided_upper_confidence_bound!), line: { color: "#255a91", width: 2.5 }, marker: { size: 9, symbol: "square" }, hovertemplate: "k=%{x}<br>Верхняя граница=%{y:.6f}<extra></extra>" }];
  return <div ref={stage} className={styles.conference}>
    <header className={styles.header}>
      <Link href="/feature-budget" className={styles.brand}>BeanFeature Lab</Link>
      <span className={styles.mode}>Научный доклад · Dry Bean</span>
      <Button onClick={full} startIcon={<IconArrowsMaximize size={19} />} color="inherit">Полный экран</Button>
      <Button component={Link} href="/feature-budget" color="inherit" className={styles.return}>К исследованию</Button>
    </header>
    <nav className={styles.progress} aria-label="Шаги научного доклада">
      {steps.map((title, index) => <button key={title} onClick={() => navigate(index)} aria-current={index === step ? "step" : undefined}><span>{index + 1}</span>{title}</button>)}
    </nav>
    <main className={styles.stage} id="main-content">
      <div className={styles.mobileStep}><span>Шаг {step + 1} из {steps.length}</span><select aria-label="Раздел доклада" value={step} onChange={e => navigate(Number(e.target.value))}>{steps.map((title, i) => <option value={i} key={title}>{title}</option>)}</select></div>
      <h1 tabIndex={-1} ref={heading}>{titles[step]}</h1>
      {fullscreenError && <Alert severity="info">{fullscreenError}</Alert>}
      {cohorts.length > 1 && <FormControl size="small"><InputLabel id="cohort-label">Группа результатов</InputLabel><Select labelId="cohort-label" label="Группа результатов" value={cohort} onChange={e => load(e.target.value)}>{cohorts.map(c => <MenuItem key={c.cohort_id} value={c.cohort_id}>{c.dataset_version} · seed {c.seed} · splits {c.outer_split_set_sha256.slice(0, 12)}</MenuItem>)}</Select></FormControl>}
      <ConferenceStatus loading={loading} error={error} expired={expired} retry={() => cohort ? load(cohort) : window.location.reload()} renew={() => load(cohort)} />
      {snapshot && !loading && <>
        {step === 0 && <div className={styles.intro}>
          <p className={styles.lead}>Как число исходных морфологических признаков влияет на классификацию семи сортов фасоли?</p>
          <div className={styles.questionAxes}><div><h2>Бюджет измерений</h2><p><strong>k исходных признаков</strong><br />Сколько измеряемых входных параметров использует процедура.</p></div><IconArrowRight size={32} aria-hidden /><div><h2>Предсказательное качество</h2><p><strong>Macro-F1</strong><br />Каждый класс имеет одинаковый вес в итоговой оценке.</p></div></div>
          <p className={styles.note}>Исследуем компромисс в качестве. Экономическая выгода меньшего числа измерений здесь не измерялась.</p>
        </div>}
        {step === 1 && <div className={styles.twoColumns}><section><p className={styles.lead}>{snapshot.dataset.rows.toLocaleString("ru-RU")} объектов, {snapshot.dataset.feature_count} исходных признаков, {snapshot.dataset.classes.length} классов.</p><p>UCI Dry Bean Dataset · ID {snapshot.dataset.source_id}. Пропуски: {snapshot.quality.missing_values}. Признаки описывают форму и геометрию семян.</p><details><summary>Canonical schema и dataset identity</summary><p>{snapshot.dataset.features.join(" · ")}</p><code>{snapshot.dataset.arff_sha256}</code><p>Официальные spellings сохранены: AspectRation, roundness, DERMASON.</p></details><a href="https://archive.ics.uci.edu/dataset/602/dry+bean+dataset" target="_blank" rel="noreferrer">Официальный источник UCI</a></section><section><h2>Распределение классов</h2><table className={styles.distribution}><thead><tr><th>Класс</th><th>Объекты</th><th>Доля</th></tr></thead><tbody>{Object.entries(snapshot.quality.class_balance).map(([label, value]) => <tr key={label}><th>{label}</th><td>{value.count.toLocaleString("ru-RU")}</td><td><span style={{ width: `${value.fraction * 100}%` }} />{(value.fraction * 100).toFixed(1)}%</td></tr>)}</tbody></table><p className={styles.note}>Macro-F1 не даёт наиболее многочисленному классу больший вес.</p></section></div>}
        {step === 2 && <><div className={styles.protocol}><section><h2>Внешняя оценка</h2><p className={styles.lead}>{snapshot.protocol.outer_splits} folds × {snapshot.protocol.outer_repeats} repeats</p><p>RepeatedStratifiedKFold. Одни и те же frozen splits для сравниваемых условий.</p></section><IconArrowRight size={28} aria-hidden /><section><h2>Внутри training fold</h2><p className={styles.lead}>{snapshot.protocol.inner_splits}-fold inner CV</p><p>StratifiedKFold с shuffle. Preprocessing, selector и поиск параметров обучаются только на training data.</p></section><IconArrowRight size={28} aria-hidden /><section><h2>Независимый outer test</h2><p className={styles.lead}>Macro-F1</p><p>Оценивается вся процедура. Test fold не участвует в выборе признаков и параметров.</p></section></div><p className={styles.note}>Модели: {baselines.map(r => modelLabel[r.configuration.model]).join(" · ")}. Accuracy, recall по классам и confusion matrices доступны в исходных fold records.</p><code>{snapshot.protocol.version}</code></>}
        {step === 3 && <><p className={styles.subtitle}>Mutual Information · среднее по outer folds. Ромбы при k=16 — baselines без отбора.</p><div className={styles.chart}><ScientificPlot presentation points={mi} baselines={baselines.map(r => ({ runId: r.run_id, model: modelLabel[r.configuration.model], macroF1: r.summary.macro_f1_mean }))} sufficient={families.filter(f => f.minimal_sufficient_k != null).map(f => ({ model: f.model, k: f.minimal_sufficient_k! }))} /></div><p className={styles.note}>Кольцо отмечает формальный sufficient-k при полной семье сравнений. Fold SD — описательная величина, не confidence interval.</p>{families.some(f => mi.filter(p => p.model === f.model).length !== 16) && <Alert severity="warning">Часть MI условий отсутствует. Неполные серии показаны отдельными проверенными точками.</Alert>}<details><summary>Численные результаты и источники</summary><ResultTable snapshot={snapshot} selector="mutual_information" /><h2>Baselines без отбора · 16 исходных признаков</h2><ResultTable snapshot={snapshot} selector="none" /></details></>}
        {step === 4 && <><div className={styles.explanation}><p>Допускается потеря не более <strong>{snapshot.protocol.margin.toFixed(2)} абсолютного Macro-F1</strong> относительно baseline той же модели с 16 исходными признаками.</p><p>Односторонняя Nadeau–Bengio correction; Bonferroni α={snapshot.protocol.family_alpha}/{snapshot.protocol.comparisons_per_model}. Решение: corrected upper loss bound ≤ δ.</p></div>{!complete && <Alert severity="warning">Не все семьи сравнений полны. Формальный минимальный sufficient-k для неполных семей не рассчитан.</Alert>}<div className={styles.sufficiencyLayout}><section><div className={styles.tableWrap}><table><thead><tr><th>Модель</th><th>Sufficient k</th><th>Upper loss bound</th><th>Сравнения</th></tr></thead><tbody>{families.map(f => <tr key={f.model}><th>{modelLabel[f.model]}</th><td>{f.minimal_sufficient_k ?? (f.status === "CALCULATED" ? "Не установлен" : "Не рассчитано")}</td><td>{metric(f.comparisons.find(c => c.k_original_features === f.minimal_sufficient_k)?.one_sided_upper_confidence_bound, 6)}</td><td>{f.calculated_comparisons}/15</td></tr>)}</tbody></table></div></section><section><FormControl size="small" className={styles.filter}><InputLabel id="bound-model">Модель</InputLabel><Select labelId="bound-model" label="Модель" value={model} onChange={e => setModel(e.target.value as ModelId)}>{families.map(f => <MenuItem key={f.model} value={f.model}>{modelLabel[f.model]}</MenuItem>)}</Select></FormControl><Button onClick={() => setCloseup(!closeup)}>{closeup ? "Показать все бюджеты 1–15" : "Приблизить бюджеты 10–15"}</Button><p className={styles.note}>{closeup ? "Детальный вид: k=10–15. Формальное решение использует всю семью 1–15." : "Полный вид: k=1–15."}</p>{upperPoints.length ? <div className={styles.lossPlot} role="img" aria-label="Corrected upper loss bound по бюджетам против margin"><Plot data={boundTraces} layout={{ autosize: true, paper_bgcolor: "#fff", plot_bgcolor: "#fff", font: { family: "Golos Text", size: 18 }, margin: { l: 95, r: 30, t: 15, b: 65 }, showlegend: false, xaxis: { title: { text: "Исходные признаки k" }, range: closeup ? [9.5, 15.5] : [0.5, 15.5], dtick: closeup ? 1 : 2 }, yaxis: { title: { text: "Upper loss bound · Macro-F1", standoff: 20 }, automargin: true, range: [lower - padding, upper + padding] }, shapes: [{ type: "line", x0: 1, x1: 15, y0: snapshot.protocol.margin, y1: snapshot.protocol.margin, line: { color: "#a5414b", dash: "dash" } }], annotations: [{ x: 15, y: snapshot.protocol.margin, text: "δ = 0.01", showarrow: false, yshift: 14 }] }} config={{ displayModeBar: false, responsive: true }} useResizeHandler style={{ width: "100%", height: "100%" }} /></div> : <Alert severity="info">Upper loss bounds для выбранных бюджетов не рассчитаны. Нужны проверенный baseline и совместимые MI runs.</Alert>}<details><summary>Все решения для выбранной модели</summary><table><thead><tr><th>k</th><th>Upper loss bound</th><th>Решение</th></tr></thead><tbody>{family?.comparisons.map(c => <tr key={c.k_original_features}><td>{c.k_original_features}</td><td>{metric(c.one_sided_upper_confidence_bound, 6)}</td><td>{c.decision === "sufficient" ? "Достаточно в протоколе" : c.decision === "not_sufficient" ? "Достаточность не установлена" : "Не рассчитано"}</td></tr>)}</tbody></table></details></section></div></>}
        {step === 5 && <><FormControl size="small" className={styles.filter}><InputLabel id="selector-label">Метод</InputLabel><Select labelId="selector-label" label="Метод" value={selector} onChange={e => setSelector(e.target.value as SelectorId)}>{(["anova", "rfe", "tree_importance", "l1_logistic", "pca"] as SelectorId[]).map(s => <MenuItem value={s} key={s}>{selectorLabel[s]}</MenuItem>)}</Select></FormControl><p className={styles.subtitle}>{selector === "pca" ? "PCA components требуют все 16 исходных измерений. Это проверка размерности, а не сокращение физических измерений." : selector === "l1_logistic" ? "L1: C задаёт регуляризацию; фактическое число ненулевых признаков различается между folds. Фиксированного k здесь нет." : "Comparator conditions — описательное сравнение. Разность средних сама по себе не доказывает статистическое превосходство."}</p>{selector !== "l1_logistic" && <div className={styles.chart}><ScientificPlot presentation points={comparisonPoints} baselines={selector === "pca" ? [] : baselines.map(r => ({ runId: r.run_id, model: modelLabel[r.configuration.model], macroF1: r.summary.macro_f1_mean }))} sufficient={[]} /></div>}{selector === "l1_logistic" ? <ResultTable snapshot={snapshot} selector={selector} /> : <details><summary>Численные результаты и источники</summary><ResultTable snapshot={snapshot} selector={selector} /></details>}</>}
        {step === 6 && <div className={styles.twoColumns}><section><h2>Результат внутри frozen protocol</h2><p className={styles.lead}>Число признаков и качество связаны с моделью и процедурой отбора.</p><p>Кривые показывают измеренные зависимости; монотонность не предполагается. Sufficient-k проверяет заданный предел потери для конкретной модели и MI.</p><p>Полные формальные семьи: {families.filter(f => f.status === "CALCULATED").length} из {families.length}. Проверенные условия в снимке: {snapshot.runs.length}.</p></section><section><h2>Граница интерпретации</h2><ul><li>Internal repeated CV; external validation не проводилась.</li><li>Sufficient-k не означает универсально оптимальный набор признаков.</li><li>Выбор признаков может различаться между training folds.</li><li>Полные исторические rank distributions и старые memory measurements недоступны.</li><li>MLP представлен baseline; Extended selectors не входят в Core.</li></ul></section></div>}
        {step === 7 && <><p className={styles.lead}>Один проверенный снимок — для доклада и научного отчёта.</p><dl className={styles.provenance}><dt>Проверено</dt><dd>{utcTime(snapshot.verified_at_utc)}</dd><dt>Срок снимка</dt><dd>{utcTime(snapshot.expires_at_utc)}</dd><dt>Dataset SHA-256</dt><dd><code>{snapshot.dataset.arff_sha256}</code></dd><dt>Outer splits SHA-256</dt><dd><code>{snapshot.cohort.outer_split_set_sha256}</code></dd><dt>Evidence SHA-256</dt><dd><code>{snapshot.evidence_sha256}</code></dd><dt>Selection</dt><dd>Самый ранний завершённый run каждого условия. Только full protocol; проверка artifacts и baseline compatibility.</dd></dl><div className={styles.actions}><Button disabled={exporting || expired} onClick={downloadPDF} variant="contained" startIcon={<IconDownload size={18} />}>{exporting ? "Формируется PDF…" : "Скачать научный PDF"}</Button><Button component={Link} href="/compare">Подробные сравнения</Button><Button component={Link} href="/runs">Run records и exports</Button></div>{pdfError && <Alert severity="error" role="alert">{pdfError}</Alert>}<p className={styles.note}>PDF содержит этот evidence snapshot: результаты, corrected sufficient-k, ограничения и индекс источников. Новый снимок не подставляется автоматически.</p><details><summary>Проверенные источники и исключённые runs</summary><div className={styles.tableWrap}><table><thead><tr><th>Run</th><th>Модель / метод</th><th>Artifact SHA-256</th></tr></thead><tbody>{snapshot.runs.map(r => <tr key={r.run_id}><td><Link href={`/runs/${r.id}`}>{r.run_id}</Link></td><td>{modelLabel[r.configuration.model]} · {selectorLabel[r.configuration.selector]}</td><td><code>{r.result_sha256}</code></td></tr>)}</tbody></table></div><p>{snapshot.excluded.map(r => `${r.run_id}: ${r.reason}`).join("; ") || "Исключённых runs нет."}</p></details></>}
      </>}
    </main>
    <footer className={styles.footer}><Button onClick={() => navigate(step - 1)} disabled={step === 0} startIcon={<IconArrowLeft size={18} />}>Назад</Button><span aria-live="polite">{step + 1} / {steps.length} · {steps[step]}</span><Button variant="contained" onClick={() => navigate(step + 1)} disabled={step === 7} endIcon={<IconArrowRight size={18} />}>Далее</Button></footer>
  </div>;
}

function ResultTable({ snapshot, selector }: { snapshot: CoreSnapshot; selector: SelectorId }) {
  const rows = snapshot.runs.filter(r => r.configuration.selector === selector);
  if (!rows.length) return <Alert severity="info">Метод не рассчитан в выбранной группе результатов.</Alert>;
  return <div className={styles.tableWrap}><table><caption>{selectorLabel[selector]} · проверенные наблюдения</caption><thead><tr><th>Модель</th><th>{selector === "pca" ? "PCA components" : selector === "l1_logistic" ? "C / observed counts" : "Исходные признаки k"}</th><th>Macro-F1</th><th>Accuracy</th><th>Run</th></tr></thead><tbody>{rows.map(r => <tr key={r.run_id}><th>{modelLabel[r.configuration.model]}</th><td>{selector === "l1_logistic" ? `C=${r.configuration.selector_configuration?.C}; folds: ${r.summary.observed_nonzero_feature_counts?.join(", ") ?? "Недоступно"}` : r.summary.k_original_features ?? r.summary.n_components}</td><td>{metric(r.summary.macro_f1_mean)}</td><td>{metric(r.summary.accuracy_mean)}</td><td><Link href={`/runs/${r.id}`}>{r.run_id}</Link></td></tr>)}</tbody></table></div>;
}
