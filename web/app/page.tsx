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
    </main>
  );
}
