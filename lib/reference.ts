// Small internal reference lists used by the engine. In a production system
// these would be large, continuously-updated datasets; here they capture the
// well-known anchors so the heuristics have something concrete to key off.

// Major centralized-exchange hot wallets on Solana. Concentration of a token
// inside a *single* one of these is a "single-exchange dominance" signal.
export const KNOWN_EXCHANGES: Record<string, string> = {
  "5tzFkiKscXHK5ZXCGbXZxdw7gTjjD1mBwuoFbhUvuAi9": "Binance",
  "9WzDXwBbmkg8ZTbNMqUxvQRAyrZzDsGYdLVL9zYtAWWM": "FTX (defunct)",
  "2ojv9BAiHUrvsm9gxDe7fJSzbNZSJcxZvf8dqmWGHG8S": "Coinbase 1",
  "H8sMJSCQxfKiFTCfDR3DUMLPwcRbM61LGFJ8N4dK3WjS": "Coinbase 2",
  "AobVSwdW9BbpMdJvTqeCN4hPAmh4rHm7vwLnQ5ATSyrS": "Kraken",
  "5PAhQiYdLBd6SVdjzBQDxUAEFyDdF5ExNPQfcscnPRj5": "OKX",
};

// Addresses whose presence in a funding path is treated as mixer / low-trust
// funding (privacy tools, sanctioned pools, throwaway bridges). Illustrative.
export const LOW_TRUST_FUNDERS = new Set<string>([
  "MixeR1111111111111111111111111111111111111",
  "TumbLe2222222222222222222222222222222222222",
]);

export function exchangeName(addr: string): string | null {
  return KNOWN_EXCHANGES[addr] ?? null;
}
