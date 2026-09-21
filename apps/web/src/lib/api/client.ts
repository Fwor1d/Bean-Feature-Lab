import type { Dataset, Experiment, Project, Run, SystemInfo } from "./contracts";

export class ApiError extends Error {
  constructor(public readonly status: number, public readonly code: string, message: string) {
    super(message);
  }
}

const baseUrl = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${baseUrl}${path}`, { ...init, cache: "no-store" });
  } catch {
    throw new ApiError(0, "api_unavailable", "API недоступен. Запустите локальный сервер и повторите запрос.");
  }
  if (!response.ok) {
    const body = await response.json().catch(() => null) as { error?: { code?: string; message?: string } } | null;
    throw new ApiError(response.status, body?.error?.code ?? "http_error", body?.error?.message ?? "Запрос не выполнен");
  }
  return response.json() as Promise<T>;
}

export const api = {
  systemInfo: () => request<SystemInfo>("/api/v1/system/info"),
  experiments: () => request<Experiment[]>("/api/v1/experiments"),
  runs: () => request<Run[]>("/api/v1/runs"),
  projects: () => request<Project[]>("/api/v1/projects"),
  datasets: () => request<Dataset[]>("/api/v1/datasets"),
  createExperiment: (body: { name: string; configuration: Experiment["configuration"] }) =>
    request<Experiment>("/api/v1/experiments", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) }),
  createRun: (experimentId: number) => request<Run>(`/api/v1/experiments/${experimentId}/runs`, { method: "POST" }),
};

export function apiErrorMessage(error: unknown): string {
  if (!(error instanceof ApiError)) return "Не удалось загрузить данные. Повторите запрос.";
  if (error.code === "api_unavailable") return error.message;
  if (error.code === "persistence_error") return "Хранилище недоступно. Проверьте миграции и работу API.";
  if (error.code === "not_found") return "Запись не найдена. Обновите список.";
  if (error.code === "validation_error" || error.code === "invalid_configuration") return "Проверьте поля конфигурации и повторите запрос.";
  return error.message;
}
