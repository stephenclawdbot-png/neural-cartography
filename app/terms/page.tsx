export const metadata = { title: "Terms of Service — Luminos" };

export default function Terms() {
  return (
    <div className="container prose">
      <h1>Terms of Service</h1>
      <p className="subtle">Demonstration terms for a clone project.</p>

      <h2>1. What Luminos is</h2>
      <p>
        Luminos is an informational tool that classifies on-chain token
        distribution patterns. It is not a broker, exchange, advisor, or custodian,
        and it never takes custody of assets.
      </p>

      <h2>2. Not financial advice</h2>
      <p>
        Nothing on this site is investment, legal, or tax advice, an offer, or a
        solicitation. Verdicts describe distribution structure only. You are solely
        responsible for your decisions.
      </p>

      <h2>3. No warranty</h2>
      <p>
        The service is provided “as is,” without warranty of any kind. Verdicts are
        heuristic and probabilistic and may be inaccurate, incomplete, or out of
        date. We do not guarantee availability, accuracy, or fitness for any
        purpose.
      </p>

      <h2>4. Limitation of liability</h2>
      <p>
        To the maximum extent permitted by law, Luminos and its operators are not
        liable for any loss or damage arising from use of, or reliance on, the
        service or any verdict it produces.
      </p>

      <h2>5. Acceptable use</h2>
      <p>
        Do not scrape, overload, or attempt to reverse-engineer signal thresholds
        for the purpose of evading classification. Automated access may be rate
        limited or blocked.
      </p>

      <h2>6. Changes</h2>
      <p>
        Signals, thresholds, and these terms may change at any time without notice.
      </p>
    </div>
  );
}
