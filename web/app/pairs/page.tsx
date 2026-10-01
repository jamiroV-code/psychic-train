import { PairsTable } from "@/components/pairs/PairsTable";

export const metadata = { title: "Pair screener" };

export default function PairsPage() {
  return (
    <main>
      <h1>Pair screener</h1>
      <PairsTable />
    </main>
  );
}
