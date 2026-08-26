"use client";

import { useState } from "react";
import { VerdictCard } from "@/components/VerdictCard";
import { DEMO_LIST } from "@/lib/demo";
import type { ScanResult } from "@/lib/types";

export default function Home() {
  const [mint, setMint] = useState("");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<ScanResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function runScan(value: string) {
    const q = value.trim();
    if (!q) {
      setError("Enter a Solana token mint address.");
      return;
    }
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      const res = await fetch(`/api/scan?mint=${encodeURIComponent(q)}`);
      const data = await res.json();
      if (!res.ok) throw new Error(data.error || "Scan failed");
      setResult(data as ScanResult);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Scan failed");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="container">
      <section className="hero">
        <span className="eyebrow">
          <span className="pulse" />
          On-chain risk scanner · Solana
        </span>
        <h1 className="hero-title">
          Is it <span className="grad">bundled</span>, cabaled,
          <br />
          or organic?
        </h1>
        <p className="sub">
          Paste a token mint. Vision reads the on-chain distribution — holder
          concentration, funding graph, and contract authorities — and classifies
          how the supply was really formed.
        </p>

        <div className="scan">
          <form
            className="scan-box"
            onSubmit={(e) => {
              e.preventDefault();
              runScan(mint);
            }}
          >
            <input
              value={mint}
              onChange={(e) => setMint(e.target.value)}
              placeholder="Solana token mint address…"
              spellCheck={false}
              autoComplete="off"
            />
            <button className="btn" type="submit" disabled={loading}>
              {loading ? "Scanning…" : "Scan"}
            </button>
          </form>

          <div className="demo-row">
            <span>Try a sample:</span>
            {DEMO_LIST.map((d) => (
              <button
                key={d.mint}
                className="chip"
                onClick={() => {
                  setMint(d.mint);
                  runScan(d.mint);
                }}
              >
                {d.symbol}
              </button>
            ))}
          </div>
        </div>

        {error && <div className="error">{error}</div>}
        {loading && (
          <div className="status">
            <span className="spinner" />
            Reading on-chain distribution…
          </div>
        )}
      </section>

      {result && <VerdictCard r={result} />}

      {!result && !loading && (
        <>
          <section className="features">
            <div className="feature amber">
              <div className="fi">◈</div>
              <h3>Bundled</h3>
              <p>
                Manufactured supply — coordinated acquisition, common funders, or
                wallets seeded through mixers and low-trust venues.
              </p>
            </div>
            <div className="feature red">
              <div className="fi">▲</div>
              <h3>Cabaled</h3>
              <p>
                Insider-shaped distribution — single-exchange dominance or supply
                concentrated among a handful of top holders.
              </p>
            </div>
            <div className="feature blue">
              <div className="fi">●</div>
              <h3>Organic</h3>
              <p>
                No coordinated pattern detected. A blue label means “nothing found,”
                not a certification of safety or a buy signal.
              </p>
            </div>
          </section>

          <p
            className="subtle"
            style={{ textAlign: "center", marginBottom: 50 }}
          >
            Dozens of independent signals, weighted for convergence. Read the{" "}
            <a href="/methodology" style={{ color: "var(--accent-2)" }}>
              methodology
            </a>
            .
          </p>
        </>
      )}
    </div>
  );
}
