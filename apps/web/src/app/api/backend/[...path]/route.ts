import { NextRequest, NextResponse } from "next/server";

const internalApi = process.env.BEANFEATURE_INTERNAL_API_BASE_URL ?? "http://127.0.0.1:8000";

async function forward(request: NextRequest, context: { params: Promise<{ path: string[] }> }) {
  const { path } = await context.params;
  if (path.length < 3 || path[0] !== "api" || path[1] !== "v1" || path.some(part => !/^[a-zA-Z0-9_-]+$/.test(part))) {
    return NextResponse.json({ error: { code: "not_found", message: "API route not found" } }, { status: 404 });
  }
  try {
    const response = await fetch(`${internalApi}/${path.join("/")}`, {
      method: request.method,
      headers: request.method === "POST" ? { "Content-Type": "application/json" } : undefined,
      body: request.method === "POST" ? await request.text() : undefined,
      cache: "no-store",
    });
    return new NextResponse(await response.text(), {
      status: response.status,
      headers: { "Content-Type": response.headers.get("Content-Type") ?? "application/json" },
    });
  } catch {
    return NextResponse.json({ error: { code: "api_unavailable", message: "Локальный API недоступен. Проверьте сервер и повторите запрос." } }, { status: 503 });
  }
}

export { forward as GET, forward as POST };
