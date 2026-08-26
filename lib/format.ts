import type { Verdict } from "./types";

export function shortAddr(a: string, size = 4): string {
  if (a.length <= size * 2 + 1) return a;
  return `${a.slice(0, size)}…${a.slice(-size)}`;
}

export function verdictLabel(v: Verdict): string {
  return { bundled: "Bundled", cabaled: "Cabaled", organic: "Organic" }[v];
}

export function verdictBlurb(v: Verdict): string {
  return {
    bundled: "Signs of manufactured supply — coordinated acquisition or common funders.",
    cabaled: "Insider-shaped distribution — concentration or single-venue dominance.",
    organic: "No coordinated pattern found. Not a buy signal or safety certification.",
  }[v];
}

/** CSS accent variable name per verdict, used across the UI. */
export function verdictAccent(v: Verdict): string {
  return { bundled: "amber", cabaled: "red", organic: "blue" }[v];
}

export function fmtPct(n: number): string {
  return `${n.toFixed(1)}%`;
}
