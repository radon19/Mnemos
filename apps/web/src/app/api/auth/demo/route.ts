import { Account, JsonRpcProvider, KeyPairSigner, type KeyPairString } from "near-api-js";
import { signMessage } from "near-api-js/nep413";
import { demoFailure, requireLocalDemo } from "@/lib/server/demo-guard";

/**
 * Local demo signer.
 *
 * This route exists so the flow can be shown without a browser wallet. It is
 * disabled unless the server has DEMO_OWNER_SECRET_KEY, the secret never
 * leaves the server, and the session it creates is marked as a demo session.
 */

const brokerUrl = (process.env.BROKER_URL ?? process.env.NEXT_PUBLIC_BROKER_URL ?? "http://localhost:8000").replace(
  /\/+$/u,
  "",
);
const rpcUrl = process.env.NEAR_RPC_URL ?? "https://test.rpc.fastnear.com";

export const dynamic = "force-dynamic";

function hexToBytes(value: string): Uint8Array {
  const bytes = new Uint8Array(value.length / 2);
  for (let index = 0; index < bytes.length; index += 1) {
    bytes[index] = Number.parseInt(value.slice(index * 2, index * 2 + 2), 16);
  }
  return bytes;
}

export async function POST(request: Request): Promise<Response> {
  try {
    requireLocalDemo(request);
    return await signInDemo();
  } catch (error) {
    return demoFailure(error);
  }
}

async function signInDemo(): Promise<Response> {
  const secretKey = process.env.DEMO_OWNER_SECRET_KEY ?? "";
  const owner = process.env.MNEMOS_OWNER_ACCOUNT ?? "";
  if (secretKey === "" || owner === "") {
    return Response.json(
      { error: "the demo signer is not configured on this server" },
      { status: 404 },
    );
  }

  const challengeResponse = await fetch(`${brokerUrl}/v1/auth/challenge`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ account: owner }),
  });
  if (!challengeResponse.ok) {
    return Response.json(
      { error: `the broker refused the challenge (${challengeResponse.status})` },
      { status: 502 },
    );
  }
  const challenge = (await challengeResponse.json()) as {
    nonce_hex: string;
    message: string;
    recipient: string;
  };

  const provider = new JsonRpcProvider({ url: rpcUrl });
  const signer = KeyPairSigner.fromSecretKey(secretKey as KeyPairString);
  const account = new Account(owner, provider, signer);
  const signed = await signMessage({
    signerAccount: account,
    payload: {
      message: challenge.message,
      nonce: hexToBytes(challenge.nonce_hex),
      recipient: challenge.recipient,
    },
  });

  const verifyResponse = await fetch(`${brokerUrl}/v1/auth/verify`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({
      account: owner,
      nonce_hex: challenge.nonce_hex,
      public_key: signed.publicKey.toString(),
      signature_b64: Buffer.from(signed.signature).toString("base64"),
    }),
  });
  if (!verifyResponse.ok) {
    return Response.json(
      { error: "The broker refused the demo signature. Check the configured owner key with make doctor." },
      { status: 502 },
    );
  }

  const session = (await verifyResponse.json()) as { account: string };
  const headers = new Headers({ "content-type": "application/json" });
  const cookie = verifyResponse.headers.get("set-cookie");
  if (cookie !== null) {
    headers.append("set-cookie", cookie);
  }
  return new Response(JSON.stringify({ account: session.account, demo: true }), { headers });
}
