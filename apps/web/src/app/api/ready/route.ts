const internalApi = process.env.BEANFEATURE_INTERNAL_API_BASE_URL ?? "http://127.0.0.1:8000";

export async function GET() {
  let available = false;
  try {
    const response = await fetch(`${internalApi}/ready`, {
      cache: "no-store",
      signal: AbortSignal.timeout(3000),
    });
    const api = await response.json();
    available = response.ok && api.application === "beanfeature-api" && api.status === "ready";
  } catch {
    // Do not expose backend URLs or exception details through the public probe.
  }
  return Response.json({ application: "beanfeature-web", status: available ? "ready" : "not_ready" }, {
    status: available ? 200 : 503,
    headers: { "Cache-Control": "no-store" },
  });
}
