"use client";

import dynamic from "next/dynamic";
import { useMediaQuery } from "@mui/material";
import type { Data, Layout } from "plotly.js";
import type { FeatureBudgetPoint, ModelId, SelectorId } from "@/lib/api/contracts";
import { modelLabel, selectorLabel } from "@/lib/science";

const Plot = dynamic(() => import("react-plotly.js"), { ssr: false });

export function ScientificPlot({ points, baselines, sufficient }: {
  points: FeatureBudgetPoint[];
  baselines: { runId: string; model: string; macroF1: number }[];
  sufficient: { model: ModelId; k: number }[];
}) {
  const narrow = useMediaQuery("(max-width: 820px)");
  const byModel = new Map<string, FeatureBudgetPoint[]>();
  for (const point of points) {
    byModel.set(point.model, [...(byModel.get(point.model) ?? []), point]);
  }
  const colors = ["#255a91", "#9a5a1c", "#2e735f", "#785391", "#a5414b"];
  const modelOrder: ModelId[] = ["logistic_regression", "svm_rbf", "random_forest", "xgboost", "lightgbm", "mlp"];
  const symbols = ["circle", "square", "triangle-up", "diamond", "cross", "star"] as const;
  const traces: Data[] = [...byModel.entries()].map(([model, unsorted], index) => {
    const values = [...unsorted].sort((a, b) => a.budget_value - b.budget_value);
    const complete = values.length === 16 && values.every((point, pointIndex) => point.budget_value === pointIndex + 1);
    const selector = values[0]?.selector as SelectorId;
    const modelIndex = modelOrder.indexOf(model as ModelId);
    const color = colors[(modelIndex < 0 ? index : modelIndex) % colors.length];
    return {
      type: "scatter", mode: complete ? "lines+markers" : "markers", name: `${modelLabel[model as FeatureBudgetPoint["model"]]} · ${selectorLabel[selector]}`,
      x: values.map(point => point.budget_value), y: values.map(point => point.macro_f1_mean),
      customdata: values.map(point => point.run_id),
      line: { width: 1.5, color },
      marker: { size: 9, color, symbol: symbols[modelIndex < 0 ? index : modelIndex] },
      hovertemplate: "k=%{x}<br>Macro-F1=%{y:.4f}<br>%{customdata}<extra>%{fullData.name}</extra>",
    };
  });
  for (const baseline of baselines) traces.push({
    type: "scatter", mode: "markers", name: `${baseline.model} · baseline 16`,
    showlegend: false,
    x: [16], y: [baseline.macroF1], customdata: [baseline.runId],
    marker: { size: 15, color: "#263c53", symbol: "diamond", line: { color: "#fff", width: 1 } },
    hovertemplate: "16 исходных признаков<br>Macro-F1=%{y:.4f}<br>%{customdata}<extra>Baseline</extra>",
  });
  for (const result of sufficient) {
    const point = points.find(item => item.model === result.model && item.budget_value === result.k);
    if (!point) continue;
    traces.push({
      type: "scatter", mode: "markers", name: `${modelLabel[result.model]} · мин. достаточное k`,
      showlegend: false,
      x: [result.k], y: [point.macro_f1_mean], customdata: [point.run_id],
      marker: { size: 20, color: "#17835c", symbol: "circle-open", line: { width: 3 } },
      hovertemplate: "Минимальное sufficient k=%{x}<br>Macro-F1=%{y:.4f}<br>%{customdata}<extra></extra>",
    });
  }
  const pca = points[0]?.budget_kind === "pca_components";
  const layout: Partial<Layout> = {
    autosize: true, paper_bgcolor: "#ffffff", plot_bgcolor: "#ffffff",
    font: { family: "Golos Text, Arial, sans-serif", size: 12, color: "#35465c" },
    margin: { l: narrow ? 52 : 72, r: 20, t: 20, b: narrow ? 155 : 105 },
    xaxis: { title: { text: pca ? "Число PCA components" : "Число исходных признаков k" }, range: [0.5, 16.5],
      tickmode: narrow ? "array" : "linear", tickvals: narrow ? [1, 4, 8, 12, 16] : undefined,
      tick0: 1, dtick: 1, gridcolor: "#e5ebf2", zeroline: false, linecolor: "#7c8999" },
    yaxis: { title: { text: "Macro-F1" }, autorange: true, tickformat: ".2f",
      gridcolor: "#e5ebf2", zeroline: false, linecolor: "#7c8999" },
    legend: { orientation: "h", x: 0, y: narrow ? -0.42 : -0.23, font: { size: 11 } },
    showlegend: traces.length > 0,
  };
  return <div className="figure-frame" role="img" aria-label={`Реальные точки Macro-F1: ${points.length} условий, ${baselines.length} baseline. Линии строятся только для полностью рассчитанных рядов 1…16.`}>
    <Plot data={traces} layout={layout} config={{ displayModeBar: false, responsive: true }} useResizeHandler style={{ width: "100%", height: "100%" }} />
    {!traces.length && <div className="plot-empty"><strong>Не рассчитано</strong><span>Научных серий пока нет</span></div>}
  </div>;
}
