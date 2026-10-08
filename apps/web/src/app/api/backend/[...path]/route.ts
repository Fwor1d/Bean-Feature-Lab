import { NextRequest, NextResponse } from "next/server";
import { isAllowedBackendPath } from "../../../../lib/api/proxy-policy";

const internalApi = process.env.BEANFEATURE_INTERNAL_API_BASE_URL ?? "http://127.0.0.1:8000";

async function boundedBody(request: NextRequest): Promise<string | null> {
  const reader = request.body?.getReader();
  if (!reader) return "";
  const chunks: Uint8Array[] = [];
  let size = 0;
  while (true) {
    const { value, done } = await reader.read();
    if (done) break;
    size += value.length;
    if (size > 32_768) { await reader.cancel(); return null; }
    chunks.push(value);
  }
  const bytes = new Uint8Array(size);
  let offset = 0;
  for (const chunk of chunks) { bytes.set(chunk, offset); offset += chunk.length; }
  return new TextDecoder().decode(bytes);
}

async function forward(request: NextRequest, context: { params: Promise<{ path: string[] }> }) {
  const { path } = await context.params;
  if (!isAllowedBackendPath(path)) {
    return NextResponse.json({ error: { code: "not_found", message: "API route not found" } }, { status: 404 });
  }
  try {
    const body = request.method === "POST" ? await boundedBody(request) : undefined;
    if (body === null) return NextResponse.json({ error: { code: "payload_too_large", message: "Запрос превышает 32 KiB." } }, { status: 413 });
    const response = await fetch(`${internalApi}/${path.join("/")}${request.nextUrl.search}`, {
      method: request.method,
      headers: request.method === "POST" ? { "Content-Type": "application/json" } : undefined,
      body,
      cache: "no-store",
      signal: AbortSignal.timeout(120_000),
    });
    const headers = new Headers({ "Content-Type": response.headers.get("Content-Type") ?? "application/json" });
    const disposition = response.headers.get("Content-Disposition");
    if (disposition) headers.set("Content-Disposition", disposition);
    for (const name of ["Cache-Control", "Retry-After", "X-Evidence-SHA256"]) {
      const value = response.headers.get(name);
      if (value) headers.set(name, value);
    }
    return new NextResponse(await response.arrayBuffer(), {
      status: response.status,
      headers,
    });
  } catch {
    return NextResponse.json({ error: { code: "api_unavailable", message: "Локальный API недоступен. Проверьте сервер и повторите запрос." } }, { status: 503 });
  }
}

export { forward as GET, forward as POST };
