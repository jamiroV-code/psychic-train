import { formatUnavailableReason } from "@/lib/format-unavailable-reason";
import type { UnavailableReason } from "@/lib/types/screener";

// discriminated union on "message" in props
type ReasonVariant  = { testId: string; reason: UnavailableReason | null; context: "timeframe" | "window"; className?: string };
type MessageVariant = { testId: string; message: string; className?: string };
export type DeadDataNoticeProps = ReasonVariant | MessageVariant;

export function DeadDataNotice(props: DeadDataNoticeProps) {
  if ("message" in props) {
    return <div data-testid={props.testId} className={props.className}>{props.message}</div>;
  }
  return (
    <div data-testid={props.testId} data-reason={props.reason ?? undefined} className={props.className}>
      {formatUnavailableReason(props.reason, props.context)}
    </div>
  );
}
