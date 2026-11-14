import type { DailyDataGap } from "@/lib/types/screener";

export function DailyDataGapNotice({ gap, showRanges = false }: {
  gap?: DailyDataGap | null;
  showRanges?: boolean;
}) {
  if (!gap || gap.missing_days === 0) return null;
  return (
    <section aria-label="Daily data gap" style={{ overflowWrap: "anywhere", minWidth: 0 }}>
      <p><strong>Daily data gap: {gap.missing_days} missing days</strong></p>
      <p>Indicators using daily history may span the missing days.</p>
      {showRanges && (
        <>
          <p>Missing date ranges (UTC, inclusive):</p>
          <ul>{gap.ranges.map(({ start, end }) => (
            <li key={start}><time dateTime={start}>{start}</time> – <time dateTime={end}>{end}</time> (UTC)</li>
          ))}</ul>
        </>
      )}
    </section>
  );
}
