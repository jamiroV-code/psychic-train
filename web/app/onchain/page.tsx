import { OnchainDashboard } from "@/components/onchain/OnchainDashboard";

export const metadata = { title: "On-chain growth" };

export default function OnchainPage() {
  return (
    <main>
      <h1>On-chain participant growth</h1>
      <OnchainDashboard />
    </main>
  );
}
