import { describe, expect, it } from "vitest";
import { DemoError, readDemoBody, requireDemoOwner, requireLocalDemo } from "../src/lib/server/demo-guard";

const env = {
  MNEMOS_LOCAL_DEMO: "true", NEXT_PUBLIC_DEMO_MODE: "true", NEAR_NETWORK: "testnet",
  NEXT_PUBLIC_NEAR_NETWORK: "testnet", MNEMOS_CONTRACT_ID: "mnemos.testnet",
  MNEMOS_OWNER_ACCOUNT: "owner.testnet",
};
const req = (headers: Record<string, string> = {}, body = "{}") => new Request("http://localhost:3000/api/demo/exchange", {
  method: "POST", headers: { host: "localhost:3000", origin: "http://localhost:3000", "content-type": "application/json", ...headers }, body,
});

describe("local demo signing boundary", () => {
  it("accepts an explicitly enabled same-origin testnet request", () => {
    expect(() => { requireLocalDemo(req(), env); }).not.toThrow();
  });
  it.each([
    { ...env, MNEMOS_LOCAL_DEMO: "false" },
    { ...env, NEXT_PUBLIC_DEMO_MODE: "false" },
    { ...env, NEAR_NETWORK: "mainnet" },
    { ...env, MNEMOS_CONTRACT_ID: "mainnet.near" },
  ])("refuses disabled or non-testnet configuration", (config) => {
    expect(() => { requireLocalDemo(req(), config); }).toThrow(DemoError);
  });
  it.each([
    { host: "attacker.example" }, { origin: "https://attacker.example" },
    { origin: "null" }, { origin: "" }, { "x-forwarded-host": "public.example" },
    { forwarded: "for=1.2.3.4" }, { "x-forwarded-for": "8.8.8.8" },
    { "sec-fetch-site": "cross-site" },
  ])("rejects remote, cross-origin and forwarded requests", (headers) => {
    expect(() => { requireLocalDemo(req(headers), env); }).toThrow(DemoError);
  });
  it("accepts Next's matching host and internal Docker source", () => {
    expect(() => { requireLocalDemo(req({ "x-forwarded-host": "localhost:3000", "x-forwarded-for": "172.18.0.1" }), env); }).not.toThrow();
  });
  it("accepts Next standalone's internal bind URL while validating the browser Host and Origin", () => {
    const request = new Request("http://0.0.0.0:3000/api/auth/demo", { method: "POST", headers: {
      host: "localhost:3000", origin: "http://localhost:3000", "x-forwarded-host": "localhost:3000", "x-forwarded-for": "::ffff:172.18.0.1",
    } });
    expect(() => { requireLocalDemo(request, { ...env, HOSTNAME: "0.0.0.0" }); }).not.toThrow();
  });
  it("requires a real owner session and passes only the session cookie", async () => {
    let sent = "";
    const fetcher = (_url: string | URL | Request, init?: RequestInit) => {
      sent = new Headers(init?.headers).get("cookie") ?? "";
      return Promise.resolve(Response.json({ account: "owner.testnet" }));
    };
    await requireDemoOwner(req({ cookie: "mnemos_session=secret; other=unrelated" }), env, fetcher);
    expect(sent).toBe("mnemos_session=secret");
    await expect(requireDemoOwner(req(), env, fetcher)).rejects.toMatchObject({ status: 401 });
    await expect(requireDemoOwner(req({ cookie: "mnemos_session=x" }), env, () => Promise.resolve(Response.json({ account: "wrong.testnet" })))).rejects.toMatchObject({ status: 403 });
  });
  it("rejects failed broker auth without forwarding its response", async () => {
    await expect(requireDemoOwner(req({ cookie: "mnemos_session=x" }), env, () => Promise.resolve(new Response("private", { status: 401 })))).rejects.toMatchObject({ status: 401 });
  });
  it("rejects invalid, oversized and incorrectly typed request bodies", async () => {
    await expect(readDemoBody(req({}, "invalid"))).rejects.toMatchObject({ status: 400 });
    await expect(readDemoBody(req({}, " ".repeat(9000)))).rejects.toMatchObject({ status: 413 });
    await expect(readDemoBody(req({ "content-type": "text/plain" }))).rejects.toMatchObject({ status: 415 });
  });
});
