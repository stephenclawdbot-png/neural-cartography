// Deterministic demo fixtures so the deployed site is fully interactive before
// any RPC keys are configured. Three tokens exercise each verdict path. These
// run through the SAME engine as live data — only the inputs are synthetic.

import type { EngineInput } from "./engine";
import type { HolderStat, TokenMeta } from "./types";

interface DemoToken {
  mint: string;
  label: string;
  meta: TokenMeta;
  holders: HolderStat[];
  funders?: Map<string, string[]>;
  deep: boolean;
}

function holders(pcts: number[], supply: number): HolderStat[] {
  return pcts.map((pct, i) => ({
    owner: `Demo${i}Wa11et${"1".repeat(30)}`.slice(0, 44),
    amount: (pct / 100) * supply,
    pct,
  }));
}

const SUPPLY = 1_000_000_000;

export const DEMO_TOKENS: Record<string, DemoToken> = {
  // Organic: flat, dispersed distribution, authorities renounced.
  "orGanicMint1111111111111111111111111111111": {
    mint: "orGanicMint1111111111111111111111111111111",
    label: "SAMPLE-ORGANIC",
    meta: {
      mint: "orGanicMint1111111111111111111111111111111",
      name: "Sample Organic",
      symbol: "ORGN",
      decimals: 6,
      supply: SUPPLY,
      mintAuthority: null,
      freezeAuthority: null,
    },
    holders: holders([4.2, 2.1, 1.8, 1.5, 1.3, 1.1, 0.9, 0.8, 0.7, 0.6], SUPPLY),
    deep: true,
    funders: new Map(),
  },

  // Cabaled: one whale + heavy top-10, mint authority still open.
  "caBaledMint111111111111111111111111111111111": {
    mint: "caBaledMint111111111111111111111111111111111",
    label: "SAMPLE-CABALED",
    meta: {
      mint: "caBaledMint111111111111111111111111111111111",
      name: "Sample Cabaled",
      symbol: "CBAL",
      decimals: 9,
      supply: SUPPLY,
      mintAuthority: "5tzFkiKscXHK5ZXCGbXZxdw7gTjjD1mBwuoFbhUvuAi9",
      freezeAuthority: null,
    },
    holders: holders([34, 18, 11, 7, 5, 3, 2, 1.5, 1, 0.8], SUPPLY),
    deep: true,
    funders: new Map(),
  },

  // Bundled: uniform mid-pack + common funder + mixer funding.
  "bundLedMint111111111111111111111111111111111": {
    mint: "bundLedMint111111111111111111111111111111111",
    label: "SAMPLE-BUNDLED",
    meta: {
      mint: "bundLedMint111111111111111111111111111111111",
      name: "Sample Bundled",
      symbol: "BNDL",
      decimals: 6,
      supply: SUPPLY,
      mintAuthority: null,
      freezeAuthority: null,
    },
    holders: holders([4.8, 3.9, 3.8, 3.7, 3.6, 3.5, 3.4, 3.3, 3.2, 3.1], SUPPLY),
    deep: true,
    funders: (() => {
      const m = new Map<string, string[]>();
      const shared = "F0nderSourceAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA";
      for (let i = 0; i < 8; i++) {
        m.set(
          `Demo${i}Wa11et${"1".repeat(30)}`.slice(0, 44),
          i < 6 ? [shared] : ["MixeR1111111111111111111111111111111111111"]
        );
      }
      return m;
    })(),
  },
};

export const DEMO_LIST = Object.values(DEMO_TOKENS).map((t) => ({
  mint: t.mint,
  label: t.label,
  symbol: t.meta.symbol,
}));

/** Map any input to a demo token. Known demo mints match exactly; anything
 *  else is routed deterministically by its first character so arbitrary input
 *  still yields a stable, plausible verdict in demo mode. */
export function pickDemo(input: string): EngineInput {
  const direct = DEMO_TOKENS[input];
  const chosen =
    direct ??
    Object.values(DEMO_TOKENS)[
      [...input].reduce((a, c) => a + c.charCodeAt(0), 0) % 3
    ];
  return {
    meta: { ...chosen.meta, mint: direct ? chosen.mint : input },
    holders: chosen.holders,
    funders: chosen.funders,
    deep: chosen.deep,
    mode: "demo",
  };
}
