import { demoFailure, readDemoBody, requireDemoOwner, requireLocalDemo } from "../../../../lib/server/demo-guard";
import { executeExchange, exchangeStatus } from "../../../../lib/server/exchange";
import { withExchangeLock } from "../../../../lib/server/exchange-lock";
import { realExchangeDeps } from "../../../../lib/server/exchange-runtime";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";
export const maxDuration = 180;

export async function GET(request: Request): Promise<Response> {
  try {
    requireLocalDemo(request);
    await requireDemoOwner(request);
    return Response.json(await exchangeStatus(realExchangeDeps()), { headers: { "cache-control": "no-store" } });
  } catch (error) { return demoFailure(error); }
}

export async function POST(request: Request): Promise<Response> {
  try {
    requireLocalDemo(request);
    await requireDemoOwner(request);
    const body = await readDemoBody(request);
    const result = await withExchangeLock(async () => executeExchange(body, realExchangeDeps()));
    return Response.json(result, { headers: { "cache-control": "no-store" } });
  } catch (error) { return demoFailure(error); }
}
