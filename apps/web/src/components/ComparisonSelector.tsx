"use client";

import { FormControl, InputLabel, MenuItem, Select } from "@mui/material";
import { useRouter } from "next/navigation";
import type { ModelId } from "@/lib/api/contracts";
import { modelLabel } from "@/lib/science";

export interface ComparisonOption {
  compactId: number;
  baselineId: number;
  compactDisplayId: string;
  baselineDisplayId: string;
  model: ModelId;
  k: number;
}

export function ComparisonSelector({ options, selected }: {
  options: ComparisonOption[];
  selected: { compactId: number; baselineId: number };
}) {
  const router = useRouter();
  const value = `${selected.compactId}:${selected.baselineId}`;
  return <FormControl size="small" sx={{ minWidth: 0, width: { xs: "100%", sm: 560 }, maxWidth: "100%", mb: 2 }}>
    <InputLabel id="comparison-condition-label">Пара условий</InputLabel>
    <Select labelId="comparison-condition-label" label="Пара условий" value={value} onChange={event => {
      const [compact, baseline] = event.target.value.split(":");
      router.push(`/compare?compact=${compact}&baseline=${baseline}`);
    }}>
      {options.map(option => <MenuItem key={`${option.compactId}:${option.baselineId}`} value={`${option.compactId}:${option.baselineId}`}>
        {modelLabel[option.model]} · MI k={option.k} → 16 baseline · {option.compactDisplayId}/{option.baselineDisplayId}
      </MenuItem>)}
    </Select>
  </FormControl>;
}
