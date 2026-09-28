import { INK } from "@/lib/onchain-view-model";

const URL_RE = /(https?:\/\/[^\s]+?)(\.?)$/;

/**
 * growthepie's CC BY attribution, rendered once per page (E6). The text is the
 * API's `attribution` string verbatim; the URL inside it becomes a link.
 */
export function SourceAttributionFooter({ attribution }: { attribution: string }) {
  const m = URL_RE.exec(attribution);
  const body = m ? (
    <>
      {attribution.slice(0, m.index)}
      <a href={m[1]} target="_blank" rel="noopener noreferrer">
        {m[1]}
      </a>
      {m[2]}
    </>
  ) : (
    attribution
  );
  return (
    <footer data-testid="onchain-attribution" style={{ fontSize: 12, color: INK.secondary, marginTop: 16 }}>
      <span data-testid="onchain-attribution-text">{body}</span>{" "}
      <span>(CC BY 4.0). L2BEAT figures are a display-only cross-check.</span>
    </footer>
  );
}
