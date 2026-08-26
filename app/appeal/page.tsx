export const metadata = { title: "Appeal a Verdict — Luminos" };

export default function Appeal() {
  return (
    <div className="container prose">
      <h1>Appeal a verdict</h1>
      <p className="lead">
        Luminos classifications are probabilistic and can be wrong. If you believe
        a token was misclassified, you can contest the verdict.
      </p>

      <h2>When an appeal makes sense</h2>
      <ul>
        <li>The funding pattern flagged as “bundled” has a documented, legitimate origin.</li>
        <li>Concentration flagged as “cabaled” reflects a known locked treasury or vesting contract.</li>
        <li>A wallet was matched to a reference list in error.</li>
      </ul>

      <h2>What to include</h2>
      <ul>
        <li>The token mint address and the verdict you are contesting.</li>
        <li>On-chain evidence — transaction signatures, vesting contract addresses, or lock proofs.</li>
        <li>A short explanation of what the classifier misread.</li>
      </ul>

      <div className="callout">
        This is a demonstration clone. In a production deployment this page would
        submit to a review queue. Appeals are reviewed against the same on-chain
        evidence the classifier uses; a re-scan may change the verdict as new data
        arrives.
      </div>

      <p className="subtle">
        Filing an appeal does not guarantee a change. Verdicts stand until the
        underlying on-chain evidence supports a different classification.
      </p>
    </div>
  );
}
