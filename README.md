# Luminos — On-Chain Risk Scanner (clone)

A Vercel-ready clone of an on-chain risk scanner for Solana tokens. Paste a token
mint and it classifies the supply distribution as **Bundled**, **Cabaled**, or
**Organic**, with a 0–100 strength score and a confidence level.

> ⚠️ This is an independent re-implementation of a publicly described methodology
> for educational/demo purposes. It classifies distribution structure only — it is
> **not financial advice** and does **not** certify any token as safe.

## How it works

```
mint ──▶ /api/scan ──▶ scanToken()
                          │
       ┌──────────────────┼───────────────────┐
       ▼                  ▼                    ▼
  getTokenMeta      getTopHolders        getFunders (deep)
  (authorities)     (concentration)      (funding graph)
       └──────────────────┼───────────────────┘
                          ▼
                     classify()  ── dozens of weighted signals,
                          │          scored for *convergence*
                          ▼
             { verdict, score, confidence, signals, holders }
```

- **Cabaled** signals: single-holder dominance, top-10 concentration,
  single-exchange dominance, active mint authority.
- **Bundled** signals: uniform mid-tier holder clusters, common funding source,
  mixer / low-trust funding.
- **Organic**: no pattern converges.

The verdict requires **convergence** — multiple independent signals agreeing — so
no single metric decides. See `lib/engine.ts`.

## Modes (graceful degradation)

| Env configured | Mode | What runs |
|---|---|---|
| _nothing_ | **demo** | Realistic sample verdicts (works instantly on Vercel) |
| `SOLANA_RPC_URL` | **live** | Real holder distribution + contract authorities |
| `+ HELIUS_API_KEY` | **live+deep** | Adds per-wallet funding-graph / bundling analysis |

Copy `.env.example` → `.env.local` (or set the vars in Vercel) to enable live
analysis. With nothing set, the site is fully interactive in demo mode.

## Local development

```bash
npm install
npm run dev        # http://localhost:3000
```

## Deploy to Vercel

1. Push this repo to GitHub (already on your branch).
2. In Vercel: **New Project → import the repo**. Framework auto-detects as Next.js.
3. (Optional) add `SOLANA_RPC_URL` and `HELIUS_API_KEY` under
   **Settings → Environment Variables** to switch from demo to live analysis.
4. Deploy. No build config needed — `vercel.json` sets the scan function timeout.

## Project layout

```
app/
  page.tsx              landing + scan flow (client)
  api/scan/route.ts     scan endpoint (serverless, node runtime)
  methodology|appeal|terms|privacy/   doc pages
components/              Header, Footer, VerdictCard
lib/
  scan.ts               orchestration (demo vs live vs deep)
  solana.ts             JSON-RPC data layer (no SDK)
  engine.ts             signal bank + classification
  reference.ts          known exchanges / low-trust funders
  demo.ts               sample fixtures
  types.ts  format.ts
```

## Notes & honest limitations

- Signal thresholds are illustrative, not tuned against a labeled dataset.
- Public RPC endpoints are heavily rate limited — use a dedicated provider for
  real traffic.
- Deep bundling analysis is bounded and best-effort; incomplete data lowers the
  reported confidence rather than failing the scan.
- Reference lists (exchanges, low-trust funders) are small illustrative stubs.
