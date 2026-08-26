import Link from "next/link";

export function Header() {
  return (
    <header className="site-header">
      <div className="container inner">
        <Link href="/" className="brand">
          <span className="dot" />
          Vision
        </Link>
        <nav className="nav">
          <Link href="/methodology">Methodology</Link>
          <Link href="/appeal">Appeal</Link>
          <Link href="/terms">Terms</Link>
          <Link href="/privacy">Privacy</Link>
        </nav>
      </div>
    </header>
  );
}
