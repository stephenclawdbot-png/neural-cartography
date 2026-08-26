import Link from "next/link";

export function Footer() {
  return (
    <footer className="site-footer">
      <div className="container inner">
        <div className="disclaimer">
          <strong style={{ color: "var(--text-dim)" }}>Vision</strong> classifies
          on-chain distribution patterns. It does not predict price, certify safety,
          or provide financial advice. Verdicts are heuristic and probabilistic and
          can be wrong. Always do your own research.
          <br />© {new Date().getFullYear()} Vision — all rights reserved.
        </div>
        <div style={{ display: "flex", gap: 18, flexWrap: "wrap" }}>
          <Link href="/methodology">Methodology</Link>
          <Link href="/appeal">Appeal</Link>
          <Link href="/terms">Terms</Link>
          <Link href="/privacy">Privacy</Link>
        </div>
      </div>
    </footer>
  );
}
