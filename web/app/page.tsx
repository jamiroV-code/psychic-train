import Link from "next/link";

export default function HomePage() {
  return (
    <main>
      <h1>Momentum Screener</h1>
      <p>
        <Link href="/screener">Open the screener board</Link>
      </p>
      <p>
        <Link href="/regime">Open the regime dashboard</Link>
      </p>
      <p>
        <Link href="/narrative" data-testid="home-link-narrative">
          Open the narrative dashboard
        </Link>
      </p>
      <p>
        <Link href="/pairs" data-testid="home-link-pairs">
          Open the pair screener
        </Link>
      </p>
      <p>
        <Link href="/onchain" data-testid="home-link-onchain">
          Open the on-chain growth dashboard
        </Link>
      </p>
    </main>
  );
}
