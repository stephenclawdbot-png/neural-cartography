// Core domain types for the on-chain risk scanner.

export type Verdict = "bundled" | "cabaled" | "organic";

export type SignalCategory = Verdict;

/** A single independent heuristic that votes toward a classification. */
export interface Signal {
  id: string;
  label: string;
  category: SignalCategory;
  /** Base importance of this signal, 0..1. */
  weight: number;
  /** Whether the signal fired for this token. */
  triggered: boolean;
  /** How strongly it fired, 0..1 (scales the weight into the vote). */
  strength: number;
  /** Human-readable explanation shown in the report. */
  detail: string;
  /** Optional raw value that drove the signal (percent, count, etc.). */
  value?: string;
}

export type ConfidenceLevel = "low" | "medium" | "high";

export interface TokenMeta {
  mint: string;
  name?: string;
  symbol?: string;
  decimals: number;
  supply: number;
  mintAuthority: string | null;
  freezeAuthority: string | null;
}

export interface HolderStat {
  /** Owner wallet (or token account when owner unavailable). */
  owner: string;
  amount: number;
  /** Percentage of circulating supply, 0..100. */
  pct: number;
}

export interface ScanResult {
  mint: string;
  verdict: Verdict;
  /** Strength of the verdict, 0..100. */
  score: number;
  confidence: ConfidenceLevel;
  /** 0..1 fraction of planned signals we had enough data to evaluate. */
  coverage: number;
  meta: TokenMeta | null;
  topHolders: HolderStat[];
  signals: Signal[];
  /** One-line summary of why this verdict was reached. */
  summary: string;
  /** Data source used to produce the result. */
  mode: "live" | "live+deep" | "demo";
  scannedAt: string;
  notes: string[];
}
