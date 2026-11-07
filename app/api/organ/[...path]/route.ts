import { NextRequest } from "next/server";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

async function proxy(request: NextRequest, context: { params: Promise<{ path: string[] }> }) {
  const { path } = await context.params;
  const target = path.join("/");
  const allowed = request.method === "POST"
    ? target === "analyses"
    : /^(health|schema|graph|trends|trends\/schema|analyses|jobs\/[a-f0-9-]{36}|analyses\/[a-f0-9-]{36})$/.test(target);
  if (!allowed) return Response.json({ detail: "Not found" }, { status: 404 });
  try {
    const base = process.env.ANALYSIS_API_URL || "http://127.0.0.1:8000";
    const body = request.method === "POST" ? await request.text() : undefined;
    if (body && body.length > 4096) return Response.json({ detail: "Request too large" }, { status: 413 });
    const query = new URLSearchParams();
    if (request.method === "GET" && target === "analyses") {
      for (const key of ["limit", "offset"]) {
        const value = request.nextUrl.searchParams.get(key);
        if (value !== null) query.set(key, value);
      }
    }
    const suffix = query.size ? `?${query}` : "";
    const response = await fetch(`${base.replace(/\/$/, "")}/${target}${suffix}`, {
      method: request.method,
      headers: { "Content-Type": "application/json" },
      body,
      cache: "no-store",
      signal: AbortSignal.timeout(15000),
    });
    return new Response(await response.text(), {
      status: response.status,
      headers: { "Content-Type": "application/json", "Cache-Control": "no-store" },
    });
  } catch {
    return Response.json({ detail: "The analysis service is unavailable. Start the Python service on port 8000." }, { status: 503 });
  }
}

export { proxy as GET, proxy as POST };
