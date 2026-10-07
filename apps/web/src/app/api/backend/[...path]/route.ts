import { NextRequest, NextResponse } from "next/server";
import { isAllowedBackendPath } from "@/lib/api/proxy-policy";

const internalApi = process.env.BEANFEATURE_INTERNAL_API_BASE_URL ?? "http://127.0.0.1:8000";

async function forward(request: NextRequest, context: { params: Promise<{ path: string[] }> }) {
  const { path } = await context.params;
  if (!isAllowedBackendPath(path)) {
    return NextResponse.json({ error: { code: "not_found", message: "API route not found" } }, { status: 404 });
  }
  try {
    const response = await fetch(`${internalApi}/${path.join("/")}`, {
      method: request.method,
      headers: request.method === "POST" ? { "Content-Type": "application/json" } : undefined,
      body: request.method === "POST" ? await request.text() : undefined,
      cache: "no-store",
    });
    const headers = new Headers({ "Content-Type": response.headers.get("Content-Type") ?? "application/json" });
    const disposition = response.headers.get("Content-Disposition");
    if (disposition) headers.set("Content-Disposition", disposition);
    return new NextResponse(await response.text(), {
      status: response.status,
      headers,
    });
  } catch {
    return NextResponse.json({ error: { code: "api_unavailable", message: "Локальный API недоступен. Проверьте сервер и повторите запрос." } }, { status: 503 });
  }
}

export { forward as GET, forward as POST };
