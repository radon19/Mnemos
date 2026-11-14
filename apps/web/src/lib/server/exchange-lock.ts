import { DemoError } from "./demo-guard";

let busy = false;

/** One laptop server, one signing operation at a time. Never queue purchases. */
export async function withExchangeLock<T>(operation: () => Promise<T>): Promise<T> {
  if (busy) throw new DemoError(409, "E_DEMO_BUSY", "Another demo action is in progress. Wait for it to finish, then refresh status.");
  busy = true;
  try { return await operation(); } finally { busy = false; }
}
