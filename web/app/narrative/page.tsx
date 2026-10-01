import { NarrativeDashboard } from "@/components/narrative/NarrativeDashboard";

export const metadata = { title: "Narrative" };

export default function NarrativePage() {
  return (
    <main>
      <h1>Narrative dashboard</h1>
      <NarrativeDashboard />
    </main>
  );
}
