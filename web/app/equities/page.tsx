import { EquitiesScreener } from "@/components/equities/EquitiesScreener";

export const metadata = { title: "Equities" };

export default function EquitiesPage() {
  return (
    <main>
      <h1>Equities</h1>
      <EquitiesScreener />
    </main>
  );
}
