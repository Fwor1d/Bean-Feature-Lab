import type { FeatureBudgetPoint, ModelId, RunStatus, SelectorId } from "./api/contracts";

/** Only points from identical official data and frozen outer folds may form one visual series. */
export function budgetCohorts(points: FeatureBudgetPoint[]): [string, FeatureBudgetPoint[]][] {
  const groups = new Map<string, FeatureBudgetPoint[]>();
  for (const point of points) {
    const key = `${point.dataset_hash}.${point.outer_split_set_sha256}`;
    groups.set(key, [...(groups.get(key) ?? []), point]);
  }
  return [...groups.entries()].sort((a, b) => b[1].length - a[1].length || a[0].localeCompare(b[0]));
}

export const modelLabel: Record<ModelId, string> = {
  logistic_regression: "Logistic Regression", svm_rbf: "SVM RBF",
  random_forest: "Random Forest", xgboost: "XGBoost", lightgbm: "LightGBM", mlp: "MLP",
};

export const selectorLabel: Record<SelectorId, string> = {
  none: "Без отбора", mutual_information: "Mutual Information", anova: "ANOVA", rfe: "RFE",
  l1_logistic: "L1 Logistic", tree_importance: "Tree importance", pca: "PCA",
  correlation_pruning: "Correlation pruning", sequential_feature_selection: "Sequential selection",
};

export function expectedBudgetConditions(selector: SelectorId): number | null {
  if (["mutual_information", "pca"].includes(selector)) return 16;
  if (["anova", "rfe", "tree_importance"].includes(selector)) return 6;
  return null;
}

export const runLabel: Record<RunStatus, string> = {
  DRAFT: "Черновик", QUEUED: "В очереди", RUNNING: "Выполняется",
  COMPLETED: "Завершён", FAILED: "Ошибка", CANCELLED: "Отменён",
};

export const metric = (value: number | null | undefined, digits = 4) =>
  value == null ? "Не рассчитано" : value.toFixed(digits);

export const utcTime = (value: string | null) =>
  value ? new Date(value).toLocaleString("ru-RU", { timeZone: "UTC", hour12: false }) + " UTC" : "—";
