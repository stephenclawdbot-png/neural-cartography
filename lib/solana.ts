// Thin Solana JSON-RPC data layer. No external SDK — plain fetch against any
// standard RPC endpoint. Everything here is best-effort and returns partial
// data rather than throwing, so the engine can lower confidence instead of
// failing outright.

import type { HolderStat, TokenMeta } from "./types";

const RPC = process.env.SOLANA_RPC_URL || "";

export function rpcConfigured(): boolean {
  return Boolean(RPC);
}

export function heliusKey(): string {
  return process.env.HELIUS_API_KEY || "";
}

interface RpcResponse<T> {
  result?: T;
  error?: { code: number; message: string };
}

async function rpc<T>(method: string, params: unknown[]): Promise<T> {
  if (!RPC) throw new Error("SOLANA_RPC_URL not configured");
  const res = await fetch(RPC, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ jsonrpc: "2.0", id: 1, method, params }),
    // RPC results are volatile; never cache.
    cache: "no-store",
  });
  if (!res.ok) throw new Error(`RPC ${method} HTTP ${res.status}`);
  const json = (await res.json()) as RpcResponse<T>;
  if (json.error) throw new Error(`RPC ${method}: ${json.error.message}`);
  if (json.result === undefined) throw new Error(`RPC ${method}: empty result`);
  return json.result;
}

/** Basic mint validation — Solana addresses are base58, 32–44 chars. */
export function isLikelyMint(s: string): boolean {
  return /^[1-9A-HJ-NP-Za-km-z]{32,44}$/.test(s.trim());
}

interface ParsedMintInfo {
  value: {
    data: {
      parsed: {
        info: {
          decimals: number;
          supply: string;
          mintAuthority: string | null;
          freezeAuthority: string | null;
        };
        type: string;
      };
      program: string;
    } | null;
  } | null;
}

export async function getTokenMeta(mint: string): Promise<TokenMeta> {
  const info = await rpc<ParsedMintInfo>("getAccountInfo", [
    mint,
    { encoding: "jsonParsed" },
  ]);
  const parsed = info?.value?.data?.parsed;
  if (!parsed || parsed.type !== "mint") {
    throw new Error("Address is not an SPL token mint");
  }
  const i = parsed.info;
  const decimals = i.decimals ?? 0;
  const supply = Number(i.supply) / Math.pow(10, decimals);
  return {
    mint,
    decimals,
    supply,
    mintAuthority: i.mintAuthority ?? null,
    freezeAuthority: i.freezeAuthority ?? null,
  };
}

interface LargestAccounts {
  value: Array<{ address: string; amount: string; uiAmount: number | null }>;
}

interface ParsedTokenAccount {
  value: {
    data: { parsed: { info: { owner: string } } } | null;
  } | null;
}

/**
 * Top holders by balance. getTokenLargestAccounts returns up to 20 token
 * accounts; we resolve each to its owner wallet and merge accounts that share
 * an owner (a common concealment trick), then rank by owned percentage.
 */
export async function getTopHolders(
  mint: string,
  supply: number
): Promise<HolderStat[]> {
  const largest = await rpc<LargestAccounts>("getTokenLargestAccounts", [mint]);
  const accounts = largest.value.filter((a) => (a.uiAmount ?? 0) > 0);

  const owners = await Promise.all(
    accounts.map(async (a) => {
      try {
        const acc = await rpc<ParsedTokenAccount>("getAccountInfo", [
          a.address,
          { encoding: "jsonParsed" },
        ]);
        return acc?.value?.data?.parsed?.info?.owner ?? a.address;
      } catch {
        return a.address; // fall back to token account address
      }
    })
  );

  const byOwner = new Map<string, number>();
  accounts.forEach((a, idx) => {
    const owner = owners[idx];
    byOwner.set(owner, (byOwner.get(owner) ?? 0) + (a.uiAmount ?? 0));
  });

  const holders: HolderStat[] = [...byOwner.entries()]
    .map(([owner, amount]) => ({
      owner,
      amount,
      pct: supply > 0 ? (amount / supply) * 100 : 0,
    }))
    .sort((a, b) => b.pct - a.pct);

  return holders;
}

/**
 * Best-effort funding-source lookup for deep bundling analysis (Helius only).
 * Returns, per wallet, the set of addresses that sent it SOL early in its life.
 * Bounded and fault-tolerant: any failure yields an empty set for that wallet.
 */
export async function getFunders(wallets: string[]): Promise<Map<string, string[]>> {
  const key = heliusKey();
  const out = new Map<string, string[]>();
  if (!key) return out;

  await Promise.all(
    wallets.map(async (w) => {
      try {
        const url = `https://api.helius.xyz/v0/addresses/${w}/transactions?api-key=${key}&type=TRANSFER&limit=20`;
        const res = await fetch(url, { cache: "no-store" });
        if (!res.ok) return;
        const txs = (await res.json()) as Array<{
          nativeTransfers?: Array<{
            fromUserAccount: string;
            toUserAccount: string;
            amount: number;
          }>;
        }>;
        const funders = new Set<string>();
        for (const tx of txs) {
          for (const nt of tx.nativeTransfers ?? []) {
            if (nt.toUserAccount === w && nt.fromUserAccount && nt.amount > 0) {
              funders.add(nt.fromUserAccount);
            }
          }
        }
        out.set(w, [...funders]);
      } catch {
        /* ignore — contributes to lower coverage */
      }
    })
  );

  return out;
}
