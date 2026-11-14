/** Local rehearsal routes are deliberately unavailable on hosted deployments. */
export class DemoError extends Error {
  constructor(readonly status: number, readonly code: string, message: string) {
    super(message);
  }
}

const LOOPBACK = new Set(["localhost", "127.0.0.1", "[::1]"]);
const MAX_BODY_BYTES = 8192;
type DemoEnvironment = Record<string, string | undefined>;

export function demoBrokerUrl(env: DemoEnvironment = process.env): string {
  return (env.BROKER_URL ?? env.NEXT_PUBLIC_BROKER_URL ?? "http://localhost:8000").replace(/\/+$/u, "");
}

export function requireLocalDemo(request: Request, env: DemoEnvironment = process.env): void {
  if (env.MNEMOS_LOCAL_DEMO !== "true" || env.NEXT_PUBLIC_DEMO_MODE !== "true") {
    throw new DemoError(404, "E_DEMO_DISABLED", "Local demo is disabled. Run make demo-ready on your laptop.");
  }
  if (env.NEAR_NETWORK !== "testnet" || env.NEXT_PUBLIC_NEAR_NETWORK !== "testnet" || !env.MNEMOS_CONTRACT_ID?.endsWith(".testnet")) {
    throw new DemoError(403, "E_TESTNET_ONLY", "The local demo only signs for a NEAR testnet contract.");
  }
  const url = new URL(request.url);
  const host = request.headers.get("host") ?? url.host;
  const hostUrl = new URL(`http://${host}`);
  const forwardedHost = request.headers.get("x-forwarded-host");
  const forwardedFor = request.headers.get("x-forwarded-for");
  // Next supplies x-forwarded-* even without a proxy. Permit its local or
  // Docker bridge source; never accept a public forwarding hop.
  const internalHop = (ip: string): boolean => /^(127\.0\.0\.1|::1|172\.(1[6-9]|2\d|3[01])\.\d+\.\d+)$/u.test(ip.trim().replace(/^::ffff:/u, ""));
  // Next standalone constructs Request.url from its bind address, not Host.
  // Only this exact internal address is accepted; browser Host stays loopback.
  const standaloneUrl = env.HOSTNAME === "0.0.0.0" && url.hostname === "0.0.0.0" && url.port === hostUrl.port;
  if ((!LOOPBACK.has(url.hostname) && !standaloneUrl) || !LOOPBACK.has(hostUrl.hostname) || (!standaloneUrl && url.host !== host) ||
      request.headers.has("forwarded") || (forwardedHost !== null && forwardedHost !== host) ||
      (forwardedFor !== null && !forwardedFor.split(",").every(internalHop)) ||
      request.headers.get("sec-fetch-site") === "cross-site") {
    throw new DemoError(403, "E_LOCAL_ONLY", "Open this demo directly at http://localhost:3000 on this laptop.");
  }
  if (request.method !== "GET" && request.headers.get("origin") !== hostUrl.origin) {
    throw new DemoError(403, "E_ORIGIN", "This action must come from the local Mnemos page. Reload it and try again.");
  }
}

export async function requireDemoOwner(
  request: Request, env: DemoEnvironment = process.env, fetcher: typeof fetch = fetch,
): Promise<void> {
  const sessionCookie = (request.headers.get("cookie") ?? "").split(";").map((part) => part.trim()).find((part) => part.startsWith("mnemos_session="));
  if (!sessionCookie) throw new DemoError(401, "E_OWNER_SESSION", "Start the local owner session first.");
  const response = await fetcher(`${demoBrokerUrl(env)}/v1/auth/session`, {
    headers: { cookie: sessionCookie }, cache: "no-store", signal: AbortSignal.timeout(10_000),
  });
  if (!response.ok) throw new DemoError(401, "E_OWNER_SESSION", "Your owner session expired. Start it again.");
  const body = await response.json() as { account?: string };
  if (body.account !== env.MNEMOS_OWNER_ACCOUNT) {
    throw new DemoError(403, "E_OWNER_MISMATCH", "This session does not belong to the configured demo owner.");
  }
}

export async function readDemoBody(request: Request): Promise<unknown> {
  if (!request.headers.get("content-type")?.startsWith("application/json")) {
    throw new DemoError(415, "E_CONTENT_TYPE", "Send this action as JSON.");
  }
  const reader = request.body?.getReader();
  if (!reader) throw new DemoError(400, "E_INVALID_INPUT", "The action body is missing.");
  const chunks: Uint8Array[] = [];
  let length = 0;
  for (;;) {
    const { value, done } = await reader.read();
    if (done) break;
    length += value.byteLength;
    if (length > MAX_BODY_BYTES) {
      await reader.cancel();
      throw new DemoError(413, "E_BODY_TOO_LARGE", "The demo request is too large.");
    }
    chunks.push(value);
  }
  try {
    return JSON.parse(Buffer.concat(chunks).toString("utf8")) as unknown;
  } catch {
    throw new DemoError(400, "E_INVALID_INPUT", "The demo request is not valid JSON.");
  }
}

export function demoFailure(error: unknown): Response {
  if (error instanceof DemoError) {
    return Response.json({ code: error.code, message: error.message }, { status: error.status, headers: { "cache-control": "no-store" } });
  }
  // Do not echo SDK error strings: upstream URLs may contain credentials.
  return Response.json({ code: "E_DEMO_DEPENDENCY", message: "A demo dependency could not be reached. Check make doctor, then refresh status before retrying." }, { status: 502 });
}
