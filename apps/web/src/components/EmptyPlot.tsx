"use client";

import dynamic from "next/dynamic";
import { Box, useMediaQuery } from "@mui/material";

const Plot = dynamic(() => import("react-plotly.js"), { ssr: false });

export function EmptyPlot({ pca = false }: { pca?: boolean }) {
  const narrow = useMediaQuery("(max-width: 820px)");
  const medium = useMediaQuery("(max-width: 1260px)");
  const ticks = narrow ? [1, 4, 8, 12, 16] : medium ? [1, 3, 5, 7, 9, 11, 13, 16] : undefined;
  return (
    <div className="plot-scroll" role="img" aria-label={`Пустая научная фигура: Macro-F1 по ${pca ? "числу компонент PCA" : "числу исходных признаков"} от 1 до 16. Результаты не рассчитаны.`}>
      <div className="figure-frame">
        <Plot data={[]} layout={{
          autosize: true, paper_bgcolor: "#ffffff", plot_bgcolor: "#ffffff",
          font: { family: "Golos Text, Arial, sans-serif", size: 12, color: "#35465c" },
          margin: { l: 72, r: 18, t: 18, b: 70 },
          xaxis: { title: { text: pca ? "Число компонент PCA" : "Число исходных признаков k" }, range: [1, 16], tickmode: ticks ? "array" : "linear", tickvals: ticks, tick0: 1, dtick: 1, showgrid: true, gridcolor: "#e5ebf2", zeroline: false, linecolor: "#7c8999", mirror: false },
          yaxis: { title: { text: "Macro-F1" }, range: [0, 1], tickmode: "linear", tick0: 0, dtick: 0.1, showgrid: true, gridcolor: "#e5ebf2", zeroline: false, linecolor: "#7c8999" },
          showlegend: false,
        }} config={{ displayModeBar: false, responsive: true }} useResizeHandler style={{ width: "100%", height: "100%" }} />
        <Box className="plot-empty" aria-hidden="true"><strong>Не рассчитано</strong><span>Научных серий пока нет</span></Box>
      </div>
    </div>
  );
}
