"use client";

import dynamic from "next/dynamic";
import type { Layout } from "plotly.js";
import { metric, selectionFrequency } from "@/lib/science";
import type { FeatureSelectionPoint } from "@/lib/api/contracts";

const Plot = dynamic(() => import("react-plotly.js"), { ssr: false, loading: () => <p role="status" className="table-note">Загрузка графика…</p> });

export function FeatureSelectionHeatmap({ features, points }: {
  features: string[];
  points: FeatureSelectionPoint[];
}) {
  const ordered = [...points].sort((a, b) => a.k_original_features - b.k_original_features);
  const layout: Partial<Layout> = {
    autosize: true,
    paper_bgcolor: "#fff",
    plot_bgcolor: "#fff",
    margin: { l: 130, r: 25, t: 12, b: 58 },
    font: { family: "Golos Text, Arial, sans-serif", size: 11, color: "#35465c" },
    xaxis: { title: { text: "Бюджет исходных признаков k" }, dtick: 1 },
    yaxis: { automargin: true },
  };
  return <><div className="figure-frame" role="img" aria-label={`Частота отбора ${features.length} признаков для ${ordered.length} рассчитанных бюджетов`}>
    <Plot
      data={[{
        type: "heatmap",
        x: ordered.map(point => point.k_original_features),
        y: features,
        z: features.map(feature => ordered.map(point => selectionFrequency(point.selection_frequency, feature))),
        zmin: 0,
        zmax: 1,
        colorscale: [[0, "#f1f4f7"], [0.5, "#77a6c9"], [1, "#174f7e"]],
        colorbar: { title: { text: "Частота" }, thickness: 12 },
        hovertemplate: "%{y}<br>k=%{x}<br>Частота=%{z:.2f}<extra></extra>",
      }]}
      layout={layout}
      config={{ displayModeBar: false, responsive: true }}
      useResizeHandler
      style={{ width: "100%", height: "100%" }}
    />
  </div><details className="stack-section"><summary>Частоты отбора — таблица значений</summary><div className="table-surface" role="region" aria-label="Таблица частот отбора по бюджетам" tabIndex={0}><table><caption>Доля outer folds; отсутствующие значения не рассчитаны</caption><thead><tr><th scope="col">Признак</th>{ordered.map(point => <th scope="col" key={point.run_id}>k={point.k_original_features}</th>)}</tr></thead><tbody>{features.map(feature => <tr key={feature}><th scope="row">{feature}</th>{ordered.map(point => <td key={point.run_id}>{metric(selectionFrequency(point.selection_frequency, feature), 2)}</td>)}</tr>)}</tbody></table></div></details></>;
}
