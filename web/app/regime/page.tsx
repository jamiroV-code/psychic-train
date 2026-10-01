import { RegimeDashboard } from "@/components/regime/RegimeDashboard";

export const metadata = { title: "Regime" };

export default function RegimePage() {
  return (
    <main>
      <h1>Regime dashboard</h1>
      <RegimeDashboard />
    </main>
  );
}
