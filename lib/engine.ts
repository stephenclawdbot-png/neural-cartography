// The classification engine. Given token metadata, holder distribution, and
// (optionally) per-wallet funding data, it runs a bank of independent signals
// and looks for CONVERGENCE — multiple signals pointing the same way — rather
// than letting any single metric decide. It emits one of three verdicts with a
// 0..100 strength score and a confidence level derived from data coverage.
//
// This is an original implementation of the publicly described methodology
// (Bundled / Cabaled / Organic). Thresholds here are deliberately illustrative.

import type {
  ConfidenceLevel,
  HolderStat,
  ScanResult,
  Signal,
  TokenMeta,
  Verdict,
} from "./types";
import { exchangeName, LOW_TRUST_FUNDERS } from "./reference";

export interface EngineInput {
  meta: TokenMeta;
  holders: HolderStat[];
  funders?: Map<string, string[]>;
  /** Whether deep (funding-graph) signals were attempted. */
  deep: boolean;
  mode: ScanResult["mode"];
}

function clamp01(x: number): number {
  return Math.max(0, Math.min(1, x));
}

/** Linear ramp: 0 below `lo`, 1 at/above `hi`. */
function ramp(x: number, lo: number, hi: number): number {
  if (hi === lo) return x >= hi ? 1 : 0;
  return clamp01((x - lo) / (hi - lo));
}

function buildSignals(input: EngineInput): { signals: Signal[]; coverage: number } {
  const { meta, holders, funders, deep } = input;
  const signals: Signal[] = [];

  const top = holders[0]?.pct ?? 0;
  const top5 = holders.slice(0, 5).reduce((s, h) => s + h.pct, 0);
  const top10 = holders.slice(0, 10).reduce((s, h) => s + h.pct, 0);

  // ---- CABALED: insider-shaped concentration -----------------------------
  signals.push({
    id: "top_holder_dominance",
    label: "Single-holder dominance",
    category: "cabaled",
    weight: 1.0,
    triggered: top >= 15,
    strength: ramp(top, 15, 40),
    detail: `Largest holder controls ${top.toFixed(1)}% of supply.`,
    value: `${top.toFixed(1)}%`,
  });

  signals.push({
    id: "top10_concentration",
    label: "Top-10 concentration",
    category: "cabaled",
    weight: 0.9,
    triggered: top10 >= 50,
    strength: ramp(top10, 50, 85),
    detail: `Top 10 wallets hold ${top10.toFixed(1)}% of supply.`,
    value: `${top10.toFixed(1)}%`,
  });

  // Single-exchange dominance: one CEX wallet holds an outsized share.
  const exchangeHolder = holders.find((h) => exchangeName(h.owner));
  const exPct = exchangeHolder?.pct ?? 0;
  signals.push({
    id: "single_exchange_dominance",
    label: "Single-exchange dominance",
    category: "cabaled",
    weight: 0.7,
    triggered: exPct >= 25,
    strength: ramp(exPct, 25, 60),
    detail: exchangeHolder
      ? `${exchangeName(exchangeHolder.owner)} wallet holds ${exPct.toFixed(1)}% — supply routed through one venue.`
      : "No single-exchange concentration detected.",
    value: exchangeHolder ? `${exPct.toFixed(1)}%` : undefined,
  });

  // ---- BUNDLED: manufactured supply --------------------------------------
  // Cluster of similarly-sized top wallets suggests split/coordinated buys.
  const midPack = holders.slice(1, 11).filter((h) => h.pct >= 1.5 && h.pct <= 6);
  const evenSpread =
    midPack.length >= 5 &&
    stddev(midPack.map((h) => h.pct)) < 1.2; // tightly clustered sizes
  signals.push({
    id: "uniform_holder_cluster",
    label: "Uniform holder cluster",
    category: "bundled",
    weight: 0.85,
    triggered: evenSpread,
    strength: evenSpread ? clamp01(midPack.length / 10) : 0,
    detail: evenSpread
      ? `${midPack.length} wallets hold near-identical stakes (${midPack[0].pct.toFixed(1)}%–${midPack[midPack.length - 1].pct.toFixed(1)}%) — a split-buy fingerprint.`
      : "No uniform mid-tier holder cluster.",
    value: evenSpread ? `${midPack.length} wallets` : undefined,
  });

  // Deep funding-graph signals (Helius). Only meaningful when `deep`.
  let commonFunderStrength = 0;
  let commonFunderDetail = "Funding-graph analysis unavailable (no deep data).";
  let mixerStrength = 0;
  let mixerDetail = "No mixer / low-trust funding observed.";
  if (deep && funders && funders.size > 0) {
    const funderCount = new Map<string, number>();
    let mixerHits = 0;
    for (const list of funders.values()) {
      for (const f of list) {
        funderCount.set(f, (funderCount.get(f) ?? 0) + 1);
        if (LOW_TRUST_FUNDERS.has(f)) mixerHits++;
      }
    }
    const shared = [...funderCount.entries()].filter(([, n]) => n >= 3);
    const maxShare = shared.reduce((m, [, n]) => Math.max(m, n), 0);
    commonFunderStrength = clamp01(maxShare / Math.max(3, funders.size));
    commonFunderDetail = shared.length
      ? `${maxShare} top wallets were funded by the same source — coordinated origin.`
      : "Top wallets have independent funding sources.";
    mixerStrength = clamp01(mixerHits / Math.max(1, funders.size));
    mixerDetail = mixerHits
      ? `${mixerHits} funding paths trace to mixer / low-trust venues.`
      : "No mixer / low-trust funding observed.";
  }

  signals.push({
    id: "common_funder",
    label: "Common funding source",
    category: "bundled",
    weight: 1.0,
    triggered: commonFunderStrength > 0.25,
    strength: commonFunderStrength,
    detail: commonFunderDetail,
  });

  signals.push({
    id: "mixer_funding",
    label: "Mixer / low-trust funding",
    category: "bundled",
    weight: 0.8,
    triggered: mixerStrength > 0,
    strength: mixerStrength,
    detail: mixerDetail,
  });

  // ---- Authority hygiene (contributes to bundled/insider risk) -----------
  const mintOpen = meta.mintAuthority !== null;
  signals.push({
    id: "mint_authority_open",
    label: "Mint authority active",
    category: "cabaled",
    weight: 0.5,
    triggered: mintOpen,
    strength: mintOpen ? 0.6 : 0,
    detail: mintOpen
      ? "Mint authority is still set — supply can be inflated at will."
      : "Mint authority renounced.",
  });

  // Coverage: fraction of signals we had real data to evaluate.
  const evaluable = signals.filter((s) => {
    if (s.id === "common_funder" || s.id === "mixer_funding") return deep && !!funders?.size;
    return true;
  }).length;
  const coverage = evaluable / signals.length;

  return { signals, coverage };
}

function stddev(xs: number[]): number {
  if (xs.length === 0) return 0;
  const mean = xs.reduce((a, b) => a + b, 0) / xs.length;
  const v = xs.reduce((a, b) => a + (b - mean) ** 2, 0) / xs.length;
  return Math.sqrt(v);
}

function confidenceFrom(coverage: number, holders: number): ConfidenceLevel {
  if (coverage >= 0.85 && holders >= 10) return "high";
  if (coverage >= 0.6 && holders >= 5) return "medium";
  return "low";
}

export function classify(input: EngineInput): ScanResult {
  const { meta, holders, mode } = input;
  const { signals, coverage } = buildSignals(input);

  // Weighted vote per category — convergence, not any single signal.
  const tally: Record<Verdict, number> = { bundled: 0, cabaled: 0, organic: 0 };
  const maxByCat: Record<Verdict, number> = { bundled: 0, cabaled: 0, organic: 0 };
  for (const s of signals) {
    const vote = s.triggered ? s.weight * s.strength : 0;
    tally[s.category] += vote;
    maxByCat[s.category] += s.weight;
  }

  const bundledScore = maxByCat.bundled ? tally.bundled / maxByCat.bundled : 0;
  const cabaledScore = maxByCat.cabaled ? tally.cabaled / maxByCat.cabaled : 0;

  let verdict: Verdict;
  let rawStrength: number;
  if (bundledScore < 0.18 && cabaledScore < 0.18) {
    verdict = "organic";
    // For organic, "score" reflects how clean it is (inverse of best risk vote).
    rawStrength = 1 - Math.max(bundledScore, cabaledScore);
  } else if (bundledScore >= cabaledScore) {
    verdict = "bundled";
    rawStrength = bundledScore;
  } else {
    verdict = "cabaled";
    rawStrength = cabaledScore;
  }

  const score = Math.round(clamp01(rawStrength) * 100);
  const confidence = confidenceFrom(coverage, holders.length);

  const fired = signals
    .filter((s) => s.triggered)
    .sort((a, b) => b.weight * b.strength - a.weight * a.strength);

  const summary =
    verdict === "organic"
      ? "No coordinated distribution pattern found. Not a safety guarantee or buy signal."
      : `${fired.length} converging signal${fired.length === 1 ? "" : "s"} indicate ${
          verdict === "bundled" ? "manufactured supply" : "insider-shaped distribution"
        }.`;

  const notes: string[] = [];
  if (!input.deep) {
    notes.push(
      "Deep funding-graph analysis was not run (no Helius key) — bundling signals are limited and confidence is capped."
    );
  }
  if (mode === "demo") {
    notes.push("DEMO result — sample data. Configure SOLANA_RPC_URL for live analysis.");
  }

  return {
    mint: meta.mint,
    verdict,
    score,
    confidence,
    coverage,
    meta,
    topHolders: holders.slice(0, 10),
    signals: signals.sort(
      (a, b) => Number(b.triggered) - Number(a.triggered) || b.weight - a.weight
    ),
    summary,
    mode,
    scannedAt: new Date().toISOString(),
    notes,
  };
}
