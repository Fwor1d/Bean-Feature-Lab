"use client";

import { FormControl, InputLabel, MenuItem, Select, Stack } from "@mui/material";
import { useRouter } from "next/navigation";
import type { ExperimentConfig } from "@/lib/api/contracts";
import { modelLabel, selectorLabel } from "@/lib/science";

export interface DescriptiveRunOption {
  id: number;
  displayId: string;
  configuration: ExperimentConfig;
}

function budgetLabel(configuration: ExperimentConfig) {
  if (configuration.budget_kind === "pca_components") return `${configuration.n_components} components`;
  if (configuration.budget_kind === "sparse_original_features") {
    return `sparse C=${String(configuration.selector_configuration?.C ?? "—")}`;
  }
  return `${configuration.k_original_features ?? "—"} признаков`;
}

function optionLabel(option: DescriptiveRunOption) {
  const config = option.configuration;
  return `${option.displayId} · ${modelLabel[config.model]} · ${selectorLabel[config.selector]} · ${budgetLabel(config)}`;
}

export function DescriptiveComparisonSelector({ options, selected }: {
  options: DescriptiveRunOption[];
  selected: { left: number; right: number };
}) {
  const router = useRouter();
  const navigate = (left: number, right: number) => {
    if (left !== right) router.push(`/compare?view=descriptive&left=${left}&right=${right}`);
  };
  return <Stack direction={{ xs: "column", md: "row" }} spacing={1.5} sx={{ mb: 2 }}>
    <FormControl size="small" fullWidth>
      <InputLabel id="left-run-label">Условие A</InputLabel>
      <Select labelId="left-run-label" label="Условие A" value={selected.left} onChange={event => navigate(Number(event.target.value), selected.right)}>
        {options.filter(option => option.id !== selected.right).map(option => <MenuItem key={option.id} value={option.id}>{optionLabel(option)}</MenuItem>)}
      </Select>
    </FormControl>
    <FormControl size="small" fullWidth>
      <InputLabel id="right-run-label">Условие B</InputLabel>
      <Select labelId="right-run-label" label="Условие B" value={selected.right} onChange={event => navigate(selected.left, Number(event.target.value))}>
        {options.filter(option => option.id !== selected.left).map(option => <MenuItem key={option.id} value={option.id}>{optionLabel(option)}</MenuItem>)}
      </Select>
    </FormControl>
  </Stack>;
}
