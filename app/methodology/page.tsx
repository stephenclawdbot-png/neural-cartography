export const metadata = { title: "Methodology — Luminos" };

export default function Methodology() {
  return (
    <div className="container prose">
      <h1>Methodology</h1>
      <p className="lead">
        Luminos is an automated distribution classifier. It sorts a token’s
        holder structure into one of three patterns. It does not predict price,
        rank quality, or certify that anything is safe.
      </p>

      <div className="callout">
        Verdicts are <strong>heuristic and probabilistic</strong>. They reflect
        the data available at scan time and can produce false positives and false
        negatives. Treat a Luminos verdict as one input among many, never as a
        decision.
      </div>

      <h2>The three classifications</h2>
      <p>
        <strong>◈ Bundled</strong> — signs of manufactured supply: coordinated
        acquisition across many wallets, a shared funding source behind the top
        holders, or wallets seeded through mixers and low-trust exchanges.
      </p>
      <p>
        <strong>▲ Cabaled</strong> — insider-shaped distribution: supply
        concentrated among a small number of top holders, or dominance by a single
        exchange venue.
      </p>
      <p>
        <strong>● Organic</strong> — no manipulation pattern detected. This is a
        statement about coordination, not a certification. It is explicitly not a
        buy signal.
      </p>

      <h2>What we read</h2>
      <ul>
        <li>
          On-chain metrics — holder balances, top-holder concentration, and the
          transfer graph between wallets.
        </li>
        <li>
          Holder relationships — connected wallets identified from funding paths
          and shared origins.
        </li>
        <li>
          Contract authorities — whether mint and freeze authority remain active.
        </li>
        <li>
          Reference data — internal lists of known exchange wallets and previously
          flagged funders.
        </li>
      </ul>

      <h2>How a verdict forms</h2>
      <p>
        Luminos runs dozens of independent signals and looks for{" "}
        <strong>convergence</strong> — several signals pointing the same way. No
        single metric decides a classification. Each scan produces:
      </p>
      <ul>
        <li>
          a <strong>classification</strong> (Bundled / Cabaled / Organic),
        </li>
        <li>
          a <strong>score</strong> from <code>0–100</code> rating the strength of
          the pattern, and
        </li>
        <li>
          a <strong>confidence</strong> level reflecting how much data was
          available.
        </li>
      </ul>
      <p>
        Exact thresholds and signal weights are withheld to make the classifier
        harder to game.
      </p>

      <h2>Confidence &amp; coverage</h2>
      <p>
        When deeper data (per-wallet funding history) is unavailable, bundling
        signals cannot be fully evaluated and confidence is capped. The report
        always shows the coverage fraction so you know how complete the analysis
        was.
      </p>

      <h2>Limitations</h2>
      <ul>
        <li>Classifications reflect a single moment and change as activity evolves.</li>
        <li>Data quality varies by token and by RPC provider.</li>
        <li>
          A clean “Organic” result does not mean a token is safe, legitimate, or a
          good investment.
        </li>
      </ul>

      <div className="callout">
        Disagree with a verdict? See the <a href="/appeal">appeal process</a>.
      </div>
    </div>
  );
}
