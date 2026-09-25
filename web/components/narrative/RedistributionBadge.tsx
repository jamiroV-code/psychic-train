/**
 * Shows a provider `redistributable` flag instead of hiding it. Renders
 * nothing when the data may be redistributed.
 */
export function RedistributionBadge({ redistributable, testId }: { redistributable: boolean; testId: string }) {
  if (redistributable) return null;
  return (
    <span
      data-testid={testId}
      data-redistributable="false"
      style={{ fontSize: 11, color: "#ff9800", border: "1px solid #ff9800", borderRadius: 3, padding: "0 4px", marginLeft: 6 }}
    >
      Personal use only — not redistributable
    </span>
  );
}
