import { PairDetailView } from "@/components/pairs/PairDetailView";

// Next 15: dynamic route params arrive as a Promise.
export async function generateMetadata({ params }: { params: Promise<{ a: string; b: string }> }) {
  const { a, b } = await params;
  return { title: `${decodeURIComponent(a)} / ${decodeURIComponent(b)}` };
}

export default async function PairDetailPage({ params }: { params: Promise<{ a: string; b: string }> }) {
  const { a, b } = await params;
  return (
    <main>
      <h1>Pair detail</h1>
      <PairDetailView a={decodeURIComponent(a)} b={decodeURIComponent(b)} />
    </main>
  );
}
