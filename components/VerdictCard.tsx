import type { ScanResult } from "@/lib/types";
import {
  fmtPct,
  shortAddr,
  verdictAccent,
  verdictLabel,
} from "@/lib/format";

const GLYPH = { bundled: "◈", cabaled: "▲", organic: "●" } as const;

const ACCENT_VAR = {
  blue: "var(--blue)",
  amber: "var(--amber)",
  red: "var(--red)",
} as const;

export function VerdictCard({ r }: { r: ScanResult }) {
  const accent = verdictAccent(r.verdict) as keyof typeof ACCENT_VAR;
  const ringColor = ACCENT_VAR[accent];
  const maxPct = Math.max(...r.topHolders.map((h) => h.pct), 1);

  return (
    <div className="result">
      <div className="verdict-card">
        <div className="verdict-head">
          <span className={`badge ${accent}`}>
            <span className="glyph">{GLYPH[r.verdict]}</span>
            {verdictLabel(r.verdict)}
          </span>
          <div className="meta-col">
            <div>
              <span className="k">Token&nbsp;</span>
              {r.meta?.symbol ? `${r.meta.symbol}` : "—"}{" "}
              <span className="k">{shortAddr(r.mint, 5)}</span>
            </div>
            <div>
              <span className="k">Confidence&nbsp;</span>
              {r.confidence.toUpperCase()}
              <span className="k">
                &nbsp;· coverage {Math.round(r.coverage * 100)}%
              </span>
            </div>
          </div>
          <div className="score-ring">
            <div
              className="ring"
              style={
                { "--p": r.score, "--c": ringColor } as React.CSSProperties
              }
            >
              <span>
                {r.score}
                <small>SCORE</small>
              </span>
            </div>
          </div>
        </div>

        <div className="verdict-body">
          <p className="summary">{r.summary}</p>
          <p className="subtle">
            {r.mode === "demo"
              ? "Demo mode"
              : r.mode === "live+deep"
              ? "Live on-chain + funding-graph analysis"
              : "Live on-chain analysis"}{" "}
            · scanned {new Date(r.scannedAt).toUTCString()}
          </p>

          <div className="section-label">Signals</div>
          {r.signals.map((s) => (
            <div
              key={s.id}
              className={`signal ${s.triggered ? "on" : "off"} ${s.category}`}
            >
              <span className="ind" />
              <div className="s-main">
                <div className="s-title">
                  {s.label}
                  <span className="cat">{s.category}</span>
                </div>
                <div className="s-detail">{s.detail}</div>
              </div>
              {s.value ? <div className="s-val">{s.value}</div> : null}
            </div>
          ))}

          {r.topHolders.length > 0 && (
            <>
              <div className="section-label">Top holders</div>
              <table className="holders">
                <thead>
                  <tr>
                    <th>#</th>
                    <th>Wallet</th>
                    <th>Share</th>
                    <th style={{ width: "34%" }}>Distribution</th>
                  </tr>
                </thead>
                <tbody>
                  {r.topHolders.map((h, i) => (
                    <tr key={h.owner + i}>
                      <td>{i + 1}</td>
                      <td>{shortAddr(h.owner, 5)}</td>
                      <td>{fmtPct(h.pct)}</td>
                      <td>
                        <div
                          className="bar"
                          style={{ width: `${(h.pct / maxPct) * 100}%` }}
                        />
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </>
          )}

          {r.meta && (
            <>
              <div className="section-label">Contract</div>
              <table className="holders">
                <tbody>
                  <tr>
                    <td>Mint authority</td>
                    <td>
                      {r.meta.mintAuthority
                        ? shortAddr(r.meta.mintAuthority, 5) + " (active ⚠)"
                        : "renounced ✓"}
                    </td>
                  </tr>
                  <tr>
                    <td>Freeze authority</td>
                    <td>
                      {r.meta.freezeAuthority
                        ? shortAddr(r.meta.freezeAuthority, 5) + " (active ⚠)"
                        : "renounced ✓"}
                    </td>
                  </tr>
                  <tr>
                    <td>Supply</td>
                    <td>{r.meta.supply.toLocaleString()}</td>
                  </tr>
                </tbody>
              </table>
            </>
          )}

          {r.notes.length > 0 && (
            <div className="notes">
              <strong>Notes</strong>
              <ul>
                {r.notes.map((n, i) => (
                  <li key={i}>{n}</li>
                ))}
              </ul>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
