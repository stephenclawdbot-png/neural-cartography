import type { Metadata } from "next";
import "./globals.css";
import { Header } from "@/components/Header";
import { Footer } from "@/components/Footer";

export const metadata: Metadata = {
  title: "Vision — On-Chain Risk Scanner for Solana Tokens",
  description:
    "Classify Solana token distribution as Bundled, Cabaled, or Organic. Heuristic, probabilistic manipulation detection — not financial advice.",
  openGraph: {
    title: "Vision — On-Chain Risk Scanner",
    description: "Bundled / Cabaled / Organic distribution classifier for Solana tokens.",
    type: "website",
  },
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        <Header />
        <main>{children}</main>
        <Footer />
      </body>
    </html>
  );
}
