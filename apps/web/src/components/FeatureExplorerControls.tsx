"use client";

import { FormControl, InputLabel, MenuItem, Select } from "@mui/material";
import { useRouter, useSearchParams } from "next/navigation";
import type { ModelId, SelectorId } from "@/lib/api/contracts";
import { modelLabel, selectorLabel } from "@/lib/science";

export function FeatureExplorerControls({ models, selectors, budgets, selected }: {
  models: ModelId[];
  selectors: SelectorId[];
  budgets: number[];
  selected: { model: ModelId; selector: SelectorId; k: number };
}) {
  const router = useRouter();
  const search = useSearchParams();
  const set = (key: string, value: string) => {
    const params = new URLSearchParams(search.toString());
    params.set(key, value);
    router.push(`/features?${params.toString()}`);
  };
  return <div className="action-row" aria-label="Условие анализа признаков">
    <FormControl size="small" sx={{ minWidth: 190 }}><InputLabel id="feature-model-label">Модель</InputLabel><Select labelId="feature-model-label" label="Модель" value={selected.model} onChange={event => set("model", event.target.value)}>{models.map(model => <MenuItem key={model} value={model}>{modelLabel[model]}</MenuItem>)}</Select></FormControl>
    <FormControl size="small" sx={{ minWidth: 190 }}><InputLabel id="feature-selector-label">Метод</InputLabel><Select labelId="feature-selector-label" label="Метод" value={selected.selector} onChange={event => set("selector", event.target.value)}>{selectors.map(selector => <MenuItem key={selector} value={selector}>{selectorLabel[selector]}</MenuItem>)}</Select></FormControl>
    <FormControl size="small" sx={{ minWidth: 145 }}><InputLabel id="feature-k-label">Бюджет k</InputLabel><Select labelId="feature-k-label" label="Бюджет k" value={selected.k} onChange={event => set("k", String(event.target.value))}>{budgets.map(k => <MenuItem key={k} value={k}>{k}</MenuItem>)}</Select></FormControl>
  </div>;
}
