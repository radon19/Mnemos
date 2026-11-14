import { demoBrokerUrl, demoFailure, DemoError, readDemoBody, requireDemoOwner, requireLocalDemo } from "@/lib/server/demo-guard";
import { withExchangeLock } from "@/lib/server/exchange-lock";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";
export const maxDuration = 240;

async function forward(request: Request, body?: unknown, action: "ask" | "refund" = "ask"): Promise<Response> {
  const cookie = (request.headers.get("cookie") ?? "").split(";").map(part => part.trim()).find(part => part.startsWith("mnemos_session=")) ?? "";
  const response = await fetch(`${demoBrokerUrl()}/v1/commerce/${body === undefined ? "status" : action}`, {
    method: body === undefined ? "GET" : "POST", cache: "no-store",
    headers: { cookie, "content-type": "application/json" },
    ...(body === undefined ? {} : { body: JSON.stringify(body) }),
    signal: AbortSignal.timeout(230_000),
  });
  const payload: unknown = await response.json();
  return Response.json(payload, { status: response.status, headers: { "cache-control": "no-store" } });
}

export async function GET(request: Request): Promise<Response> {
  try {
    requireLocalDemo(request);
    await requireDemoOwner(request);
    return await forward(request);
  } catch (error) { return demoFailure(error); }
}

export async function POST(request: Request): Promise<Response> {
  try {
    requireLocalDemo(request);
    await requireDemoOwner(request);
    const body = await readDemoBody(request);
    if (!body || typeof body !== "object" || Array.isArray(body)) throw new DemoError(400, "E_INVALID_INPUT", "Send a purchase request.");
    const value = body as Record<string, unknown>;
    if (Object.keys(value).length === 2 && value.action === "refund" && typeof value.read_id === "string" && /^[0-9a-f-]{36}$/u.test(value.read_id)) {
      return await withExchangeLock(async () => forward(request, { read_id: value.read_id }, "refund"));
    }
    if (Object.keys(value).length !== 3 || value.scope !== "expertise" ||
        typeof value.read_id !== "string" || !/^[0-9a-f-]{36}$/u.test(value.read_id) ||
        typeof value.question !== "string" || !value.question.trim() || value.question.length > 2000) {
      throw new DemoError(400, "E_INVALID_INPUT", "Choose an expertise question and a valid purchase ID.");
    }
    return await withExchangeLock(async () => forward(request, value));
  } catch (error) { return demoFailure(error); }
}
