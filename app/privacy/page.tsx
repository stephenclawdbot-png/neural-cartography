export const metadata = { title: "Privacy Policy — Luminos" };

export default function Privacy() {
  return (
    <div className="container prose">
      <h1>Privacy Policy</h1>
      <p className="subtle">Demonstration policy for a clone project.</p>

      <h2>What we process</h2>
      <p>
        Luminos analyzes <strong>public blockchain data</strong>. When you scan a
        token, the mint address you submit is sent to our API and to the configured
        Solana RPC provider to retrieve on-chain state. We do not ask for, or need,
        your identity or wallet connection to run a scan.
      </p>

      <h2>What we don’t collect</h2>
      <ul>
        <li>No wallet connection is required and none is requested.</li>
        <li>No private keys, seed phrases, or signatures — ever.</li>
        <li>No account is needed to use the scanner.</li>
      </ul>

      <h2>Third parties</h2>
      <p>
        Scans rely on external infrastructure (a Solana RPC endpoint and,
        optionally, an indexing provider such as Helius). Mint addresses you scan
        are shared with those providers to fetch on-chain data, subject to their
        own policies. Hosting is provided by the deployment platform (e.g. Vercel).
      </p>

      <h2>Logs</h2>
      <p>
        Standard server logs (timestamps, requested endpoints, error traces) may be
        retained for reliability and abuse prevention. This clone does not set
        tracking cookies.
      </p>

      <h2>Contact</h2>
      <p>
        This is a demonstration deployment. Configure a real contact channel before
        using it in production.
      </p>
    </div>
  );
}
