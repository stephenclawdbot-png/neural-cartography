// Orchestration: decide demo vs. live vs. deep, gather data, run the engine.

import { classify, type EngineInput } from "./engine";
import { pickDemo } from "./demo";
import type { ScanResult } from "./types";
import {
  getFunders,
  getTokenMeta,
  getTopHolders,
  heliusKey,
  isLikelyMint,
  rpcConfigured,
} from "./solana";

function demoForced(): boolean {
  return process.env.VISION_DEMO_MODE === "true";
}

export async function scanToken(rawInput: string): Promise<ScanResult> {
  const input = rawInput.trim();
  if (!input) throw new Error("Provide a token mint address.");

  // Demo mode: no RPC configured, or explicitly forced.
  if (demoForced() || !rpcConfigured()) {
    return classify(pickDemo(input));
  }

  if (!isLikelyMint(input)) {
    throw new Error("That doesn't look like a Solana mint address.");
  }

  // Live path.
  const meta = await getTokenMeta(input);
  const holders = await getTopHolders(input, meta.supply);

  const deep = Boolean(heliusKey());
  let funders: Map<string, string[]> | undefined;
  if (deep) {
    const wallets = holders.slice(0, 10).map((h) => h.owner);
    funders = await getFunders(wallets);
  }

  const engineInput: EngineInput = {
    meta,
    holders,
    funders,
    deep: deep && Boolean(funders && funders.size > 0),
    mode: deep ? "live+deep" : "live",
  };

  return classify(engineInput);
}
